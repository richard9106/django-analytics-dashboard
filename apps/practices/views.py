import secrets

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .forms import DropboxIntegrationForm, GmailSendForm, GoogleOAuthSelectionForm
from .google_oauth import (
    build_google_authorization_url,
    exchange_google_code,
    fetch_google_account_email,
    list_calendar_events,
    list_gmail_messages,
    send_gmail_message,
    token_expiry_from_response,
)
from .models import ExternalIntegration


class PracticeContextMixin(LoginRequiredMixin, ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)


class IntegrationSettingsView(PracticeContextMixin, TemplateView):
    template_name = 'settings/integrations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        integrations = {
            integration.provider: integration
            for integration in ExternalIntegration.objects.filter(practice=practice)
        } if practice else {}
        context['practice'] = practice
        context['google_integration'] = integrations.get(ExternalIntegration.Provider.GOOGLE)
        context['dropbox_integration'] = integrations.get(ExternalIntegration.Provider.DROPBOX)
        context['google_form'] = GoogleOAuthSelectionForm(instance=context['google_integration'])
        context['dropbox_form'] = DropboxIntegrationForm(instance=context['dropbox_integration'], practice=practice)
        context['google_oauth_configured'] = bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)
        return context


class GoogleOAuthConnectView(PracticeContextMixin, View):
    def post(self, request):
        if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
            raise PermissionDenied('Google OAuth is not configured.')

        practice = self.get_practice()
        integration = ExternalIntegration.objects.filter(practice=practice, provider=ExternalIntegration.Provider.GOOGLE).first()
        form = GoogleOAuthSelectionForm(request.POST, instance=integration)
        if not form.is_valid():
            return redirect('practice_settings:integrations')

        integration = form.save(commit=False)
        integration.practice = practice
        integration.provider = ExternalIntegration.Provider.GOOGLE
        integration.enabled_scopes = form.get_enabled_scopes()
        integration.oauth_state = secrets.token_urlsafe(32)
        integration.status = ExternalIntegration.Status.DISCONNECTED
        integration.full_clean()
        integration.save()
        request.session['google_oauth_state'] = integration.oauth_state
        request.session['google_oauth_integration_id'] = integration.pk
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'practices.ExternalIntegration',
            integration.pk,
            practice=practice,
            metadata={'provider': 'google', 'connect_started': True, 'enabled_scopes': integration.enabled_scopes},
        )
        return redirect(build_google_authorization_url(request, integration.enabled_scopes, integration.oauth_state))


class GoogleOAuthCallbackView(PracticeContextMixin, View):
    def get(self, request):
        state = request.GET.get('state')
        code = request.GET.get('code')
        expected_state = request.session.get('google_oauth_state')
        integration_id = request.session.get('google_oauth_integration_id')
        if not state or not code or state != expected_state or not integration_id:
            raise PermissionDenied('Invalid Google OAuth state.')

        practice = self.get_practice()
        integration = ExternalIntegration.objects.get(pk=integration_id, practice=practice, provider=ExternalIntegration.Provider.GOOGLE)
        if integration.oauth_state != state:
            raise PermissionDenied('Invalid Google OAuth state.')

        token_response = exchange_google_code(request, code)
        access_token = token_response.get('access_token', '')
        integration.access_token = access_token
        integration.refresh_token = token_response.get('refresh_token', integration.refresh_token)
        integration.granted_scopes = token_response.get('scope', '').split()
        integration.token_expires_at = token_expiry_from_response(token_response)
        integration.account_email = fetch_google_account_email(access_token) if access_token else ''
        integration.status = ExternalIntegration.Status.CONNECTED
        integration.connected_at = timezone.now()
        integration.oauth_state = ''
        integration.full_clean()
        integration.save()
        request.session.pop('google_oauth_state', None)
        request.session.pop('google_oauth_integration_id', None)
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'practices.ExternalIntegration',
            integration.pk,
            practice=practice,
            metadata={'provider': 'google', 'connected': True, 'granted_scopes': integration.granted_scopes},
        )
        return redirect('practice_settings:integrations')


class GoogleOAuthDisconnectView(PracticeContextMixin, View):
    def post(self, request):
        practice = self.get_practice()
        integration = ExternalIntegration.objects.filter(practice=practice, provider=ExternalIntegration.Provider.GOOGLE).first()
        if integration:
            integration.disconnect()
            integration.send_email_enabled = False
            integration.read_email_enabled = False
            integration.calendar_enabled = False
            integration.file_storage_enabled = False
            integration.save()
            log_audit_event(
                request,
                AuditLog.Action.UPDATE,
                'practices.ExternalIntegration',
                integration.pk,
                practice=practice,
                metadata={'provider': 'google', 'disconnected': True},
            )
        return redirect('practice_settings:integrations')


class DropboxIntegrationUpdateView(PracticeContextMixin, View):
    def post(self, request):
        practice = self.get_practice()
        integration = ExternalIntegration.objects.filter(practice=practice, provider=ExternalIntegration.Provider.DROPBOX).first()
        form = DropboxIntegrationForm(request.POST, instance=integration, practice=practice)
        if form.is_valid():
            integration = form.save()
            log_audit_event(
                request,
                AuditLog.Action.UPDATE,
                'practices.ExternalIntegration',
                integration.pk,
                practice=practice,
                metadata={'provider': 'dropbox', 'file_storage_enabled': integration.file_storage_enabled},
            )
        return redirect('practice_settings:integrations')


class GoogleWorkspaceView(PracticeContextMixin, TemplateView):
    template_name = 'settings/google_workspace.html'

    def get_integration(self):
        practice = self.get_practice()
        return ExternalIntegration.objects.filter(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
        ).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        integration = self.get_integration()
        context['google_integration'] = integration
        context['send_form'] = kwargs.get('send_form') or GmailSendForm()
        context['gmail_messages'] = []
        context['calendar_events'] = []
        context['google_error'] = ''
        if not integration:
            context['google_error'] = 'Connect Google first.'
            return context
        try:
            if integration.read_email_enabled:
                context['gmail_messages'] = list_gmail_messages(integration)
            if integration.calendar_enabled:
                context['calendar_events'] = list_calendar_events(integration)
        except Exception as error:
            context['google_error'] = str(error)
        return context


class GmailSendView(PracticeContextMixin, View):
    def post(self, request):
        practice = self.get_practice()
        integration = ExternalIntegration.objects.filter(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            send_email_enabled=True,
        ).first()
        if not integration:
            raise PermissionDenied('Google Gmail send is not connected.')
        form = GmailSendForm(request.POST)
        if form.is_valid():
            send_gmail_message(
                integration,
                form.cleaned_data['to_email'],
                form.cleaned_data['subject'],
                form.cleaned_data['body'],
            )
            log_audit_event(
                request,
                AuditLog.Action.CREATE,
                'google.GmailMessage',
                practice=practice,
                metadata={'to_email': form.cleaned_data['to_email'], 'subject': form.cleaned_data['subject']},
            )
            return redirect('practice_settings:google_workspace')
        view = GoogleWorkspaceView()
        view.request = request
        return view.render_to_response(view.get_context_data(send_form=form), status=400)
