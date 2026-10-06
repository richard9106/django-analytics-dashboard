import base64
import io
import time
import uuid
from urllib.parse import urlencode

import pyotp
import qrcode
from cryptography.fernet import InvalidToken
from django import forms
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator

from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.rate_limit import PostRateLimitMixin
from .models import AccountSecurity
from .security import (confirm_enrollment, decrypt_session_value, encrypt_session_value,
                       establish_session, new_recovery_codes, requires_mfa,
                       safe_next, security_state, verified, verify_factor)


class CodeForm(forms.Form):
    code = forms.CharField(label='Authenticator or recovery code', max_length=64,
                          widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'one-time-code', 'autofocus': True}))


class PasswordCodeForm(CodeForm):
    password = forms.CharField(label='Current password', strip=False,
                               widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


def audit_security(request, event):
    log_audit_event(request, AuditLog.Action.UPDATE, 'accounts.AccountSecurity', request.user.pk,
                    metadata={'event': event})


def issue_codes(request, codes):
    # Never keep readable recovery codes in the session table or a URL.
    request.session['mfa_codes'] = encrypt_session_value(codes)
    return redirect('mfa_recovery_codes')


@method_decorator(sensitive_post_parameters('password', 'code'), name='dispatch')
class MFASetupView(LoginRequiredMixin, PostRateLimitMixin, FormView):
    template_name = 'accounts/security_setup.html'
    form_class = PasswordCodeForm
    rate_limit_scope = 'mfa-setup'
    rate_limit_count = 15
    rate_limit_seconds = 900

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            state = security_state(request.user)
            if not requires_mfa(request.user):
                return redirect('security_settings')
            if state.confirmed:
                if not verified(request, state):
                    return redirect('mfa_challenge')
                if request.GET.get('replace') != '1':
                    return redirect('security_settings')
                if time.time() - request.session.get('security_auth_at', 0) >= settings.SECURITY_REAUTH_TIMEOUT:
                    return redirect(reverse('security_reauthenticate') + '?' + urlencode({'next': request.get_full_path()}))
            self.state = state
        return super().dispatch(request, *args, **kwargs)

    def pending(self):
        pending = self.request.session.get('mfa_pending')
        if not pending or time.time() - pending['started'] >= settings.SECURITY_CHALLENGE_TIMEOUT or pending['version'] != str(self.state.session_version):
            pending = {'secret': encrypt_session_value(pyotp.random_base32()), 'started': time.time(),
                       'version': str(self.state.session_version), 'replace': self.state.confirmed}
            self.request.session['mfa_pending'] = pending
        return pending

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        secret = decrypt_session_value(self.pending()['secret'])
        uri = pyotp.TOTP(secret).provisioning_uri(self.request.user.email or self.request.user.username, issuer_name='NuviaMy')
        output = io.BytesIO()
        qrcode.make(uri).save(output, format='PNG')
        context.update({'setup_key': secret, 'qr_image': base64.b64encode(output.getvalue()).decode()})
        return context

    def form_valid(self, form):
        # Do not silently renew an expired enrollment when submitting its code.
        pending = self.request.session.get('mfa_pending')
        if not pending or time.time() - pending['started'] >= settings.SECURITY_CHALLENGE_TIMEOUT:
            self.request.session.pop('mfa_pending', None)
            form.add_error(None, 'Setup expired. Scan the new QR code and try again.')
            return self.form_invalid(form)
        try:
            secret = decrypt_session_value(pending['secret'])
        except InvalidToken:
            self.request.session.pop('mfa_pending', None)
            form.add_error(None, 'Setup expired. Please try again.')
            return self.form_invalid(form)
        enrollment = confirm_enrollment(self.request.user, secret, form.cleaned_data['code'],
                                   form.cleaned_data['password'], pending['version'], pending['replace'])
        if enrollment is None:
            audit_security(self.request, 'mfa_setup_failed')
            form.add_error(None, 'Password or code is invalid, already used, or temporarily locked. Try again later.')
            return self.form_invalid(form)
        self.request.session.pop('mfa_pending', None)
        codes, verified_state = enrollment
        establish_session(self.request, verified_state, mfa=True)
        audit_security(self.request, 'mfa_enrolled')
        return issue_codes(self.request, codes)


@method_decorator(sensitive_post_parameters('code'), name='dispatch')
class MFAChallengeView(LoginRequiredMixin, PostRateLimitMixin, FormView):
    template_name = 'accounts/security_challenge.html'
    form_class = CodeForm
    rate_limit_scope = 'mfa-challenge'
    rate_limit_count = 20
    rate_limit_seconds = 900

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            state = security_state(request.user)
            if not requires_mfa(request.user) or verified(request, state):
                return redirect(safe_next(request))
            if not state.confirmed:
                return redirect('mfa_setup')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        verified_state = verify_factor(self.request.user, form.cleaned_data['code'])
        if not verified_state:
            audit_security(self.request, 'mfa_challenge_failed')
            form.add_error(None, 'Code is invalid, already used, or temporarily locked. Try again later.')
            return self.form_invalid(form)
        establish_session(self.request, verified_state, mfa=True)
        audit_security(self.request, 'mfa_verified')
        return redirect(safe_next(self.request))


class RecoveryCodesView(LoginRequiredMixin, View):
    def get(self, request):
        value = request.session.pop('mfa_codes', None)
        if not value:
            return redirect('security_settings')
        return render(request, 'accounts/security_codes.html', {'codes': decrypt_session_value(value), 'continue_url': safe_next(request)})


@method_decorator(sensitive_post_parameters('password', 'code'), name='dispatch')
class ReauthenticateView(LoginRequiredMixin, PostRateLimitMixin, FormView):
    template_name = 'accounts/security_reauthenticate.html'
    form_class = PasswordCodeForm
    rate_limit_scope = 'reauthenticate'
    rate_limit_count = 15
    rate_limit_seconds = 900

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not requires_mfa(self.request.user):
            form.fields.pop('code')
        return form

    def form_valid(self, form):
        user = self.request.user
        state = security_state(user)
        if requires_mfa(user):
            valid = verify_factor(user, form.cleaned_data['code'], form.cleaned_data['password'])
        else:
            valid = user.check_password(form.cleaned_data['password'])
        if not valid:
            audit_security(self.request, 'reauthentication_failed')
            form.add_error(None, 'Credentials are invalid, already used, or temporarily locked.')
            return self.form_invalid(form)
        establish_session(self.request, valid if requires_mfa(user) else state, mfa=requires_mfa(user))
        audit_security(self.request, 'reauthenticated')
        candidate = self.request.GET.get('next')
        if candidate == '/accounts/security/setup/?replace=1':
            return redirect(candidate)
        return redirect(safe_next(self.request, candidate))


@method_decorator(sensitive_post_parameters('password', 'code'), name='dispatch')
class SecuritySettingsView(LoginRequiredMixin, PostRateLimitMixin, FormView):
    template_name = 'accounts/security_settings.html'
    form_class = PasswordCodeForm
    rate_limit_scope = 'security-settings'
    rate_limit_count = 15
    rate_limit_seconds = 900

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not requires_mfa(self.request.user):
            form.fields.pop('code')
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        state = security_state(self.request.user)
        context.update({'mfa_required': requires_mfa(self.request.user), 'recovery_count': len(state.recovery_hashes)})
        return context

    @transaction.atomic
    def form_valid(self, form):
        action = self.request.POST.get('action')
        if action not in {'recovery_codes', 'revoke_sessions'} or (action == 'recovery_codes' and not requires_mfa(self.request.user)):
            form.add_error(None, 'Unknown security action.')
            return self.form_invalid(form)
        user = self.request.user
        if requires_mfa(user):
            valid = verify_factor(user, form.cleaned_data['code'], form.cleaned_data['password'])
        else:
            valid = user.check_password(form.cleaned_data['password'])
        if not valid:
            audit_security(self.request, 'security_action_failed')
            form.add_error(None, 'Credentials are invalid, already used, or temporarily locked.')
            return self.form_invalid(form)
        state = AccountSecurity.objects.select_for_update().get(user=user)
        codes = new_recovery_codes(state) if action == 'recovery_codes' else None
        state.session_version = uuid.uuid4()
        state.save()
        establish_session(self.request, state, mfa=requires_mfa(user))
        audit_security(self.request, action)
        if codes:
            return issue_codes(self.request, codes)
        return redirect('security_settings')


class SecuritySessionView(LoginRequiredMixin, View):
    def post(self, request):
        return JsonResponse({'authenticated': True, 'idle_seconds': settings.SECURITY_IDLE_TIMEOUT})
