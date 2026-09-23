from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .forms import ExternalIntegrationForm
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
        context['integration_cards'] = [
            {
                'provider': provider,
                'label': label,
                'integration': integrations.get(provider),
                'form': ExternalIntegrationForm(
                    instance=integrations.get(provider),
                    practice=practice,
                    provider=provider,
                    prefix=provider,
                ),
            }
            for provider, label in ExternalIntegration.Provider.choices
        ]
        return context


class IntegrationUpdateView(PracticeContextMixin, View):
    def post(self, request, provider):
        valid_providers = {choice for choice, _label in ExternalIntegration.Provider.choices}
        if provider not in valid_providers:
            return redirect('practice_settings:integrations')
        practice = self.get_practice()
        integration = ExternalIntegration.objects.filter(practice=practice, provider=provider).first()
        form = ExternalIntegrationForm(
            request.POST,
            instance=integration,
            practice=practice,
            provider=provider,
            prefix=provider,
        )
        if form.is_valid():
            integration = form.save()
            log_audit_event(
                request,
                AuditLog.Action.UPDATE,
                'practices.ExternalIntegration',
                integration.pk,
                practice=practice,
                metadata={'provider': integration.provider, 'status': integration.status},
            )
        return redirect('practice_settings:integrations')
