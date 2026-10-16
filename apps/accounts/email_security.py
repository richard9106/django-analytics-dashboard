"""Single-use, session-bound email verification; plaintext codes are never persisted."""
import secrets
import time
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView

from apps.rate_limit import PostRateLimitMixin
from .models import AccountSecurity
from .security import safe_next


def binding(request):
    user = request.user
    return salted_hmac('email-login-binding', '\x00'.join((str(user.pk), user.email.casefold(), user.password,
        str(request.account_security.session_version)))).hexdigest()


def email_verified(request):
    return constant_time_compare(request.session.get('email_verified_binding', ''), binding(request))


def code_digest(challenge, code):
    return salted_hmac('email-login-code', challenge + ':' + code, algorithm='sha256').hexdigest()


class EmailCodeForm(forms.Form):
    code = forms.RegexField(r'^[0-9]{6}$', label='Verification code', max_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code',
                                     'autofocus': True, 'placeholder': '000000'}),
        error_messages={'invalid': 'Enter the 6-digit code from your email.'})


@method_decorator(sensitive_post_parameters('code'), name='dispatch')
class EmailChallengeView(LoginRequiredMixin, PostRateLimitMixin, FormView):
    template_name = 'accounts/email_challenge.html'
    form_class = EmailCodeForm
    rate_limit_scope = 'email-login'
    rate_limit_count = 30
    rate_limit_seconds = 900
    notice = ''

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and (not settings.EMAIL_TWO_STEP_REQUIRED or email_verified(request)):
            return redirect(safe_next(request))
        return super().dispatch(request, *args, **kwargs)

    def send_code(self):
        request = self.request
        now = timezone.now()
        challenge = request.session.get('email_challenge_id') or secrets.token_urlsafe(32)
        request.session['email_challenge_id'] = challenge
        with transaction.atomic():
            state = AccountSecurity.objects.select_for_update().get(user=request.user)
            if state.blocked_until and state.blocked_until > now:
                self.notice = 'Too many attempts. Please wait 15 minutes before trying again.'
                return
            if state.email_code_sent_at and now - state.email_code_sent_at < timedelta(seconds=60):
                self.notice = 'You can request another code after 60 seconds.'
                return
            code = f'{secrets.randbelow(1000000):06d}'
            state.email_code_hash = code_digest(challenge, code)
            state.email_code_binding = binding(request)
            state.email_code_sent_at = now
            state.email_code_attempts = 0
            state.save(update_fields=['email_code_hash', 'email_code_binding', 'email_code_sent_at', 'email_code_attempts'])
            try:
                if not request.user.email:
                    raise ValueError('No delivery address')
                sent = send_mail('Your NuviaMy sign-in code',
                    f'Your sign-in code is {code}.\n\nIt expires in 10 minutes and can only be used once. '
                    'Do not share this code. If you did not try to sign in, change your password or contact support.',
                    settings.DEFAULT_FROM_EMAIL, [request.user.email], fail_silently=False)
                if not sent:
                    raise ValueError('Delivery unavailable')
            except Exception:
                # Do not log SMTP exceptions: they can contain credentials or message content.
                state.email_code_hash = ''
                state.save(update_fields=['email_code_hash'])
                self.notice = 'We could not send the code. Please try again shortly or contact support.'
                return
        self.notice = 'A code was sent. Use the most recent code.'

    def get(self, request, *args, **kwargs):
        if not request.session.get('email_challenge_id'):
            self.send_code()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'resend':
            self.send_code()
            return self.render_to_response(self.get_context_data(form=self.form_class()))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        now = timezone.now()
        error = 'That code is incorrect or expired. Request a new code if needed.'
        with transaction.atomic():
            state = AccountSecurity.objects.select_for_update().get(user=self.request.user)
            if state.blocked_until and state.blocked_until > now:
                error = 'Too many attempts. Please wait 15 minutes before trying again.'
            else:
                valid = (state.email_code_hash and state.email_code_sent_at
                    and now - state.email_code_sent_at < timedelta(minutes=10)
                    and constant_time_compare(state.email_code_binding, binding(self.request))
                    and constant_time_compare(state.email_code_hash,
                        code_digest(self.request.session.get('email_challenge_id', ''), form.cleaned_data['code'])))
                if valid:
                    state.email_code_hash = ''
                    state.email_code_attempts = 0
                    state.save(update_fields=['email_code_hash', 'email_code_attempts'])
                    self.request.session.cycle_key()
                    self.request.session['email_verified_binding'] = binding(self.request)
                    self.request.session['security_auth_at'] = time.time()
                    from .security_views import audit_security
                    audit_security(self.request, 'email_sign_in_verified')
                    return redirect(safe_next(self.request))
                state.email_code_attempts += 1
                if state.email_code_attempts >= 5:
                    state.blocked_until = now + timedelta(minutes=15)
                    state.email_code_hash = ''
                    error = 'Too many attempts. Please wait 15 minutes before trying again.'
                state.save(update_fields=['email_code_attempts', 'blocked_until', 'email_code_hash'])
        from .security_views import audit_security
        audit_security(self.request, 'email_sign_in_rejected')
        form.add_error('code', error)
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        email = self.request.user.email
        local, _, domain = email.partition('@')
        context.update(masked_email=(local[:1] + '••••@' + domain) if domain else 'your account email', notice=self.notice)
        return context
