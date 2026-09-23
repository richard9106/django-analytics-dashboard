from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.billing.models import Invoice, ServicePackage
from apps.documents.models import ClientDocument
from .forms import ClientPortalAccessForm, suggest_portal_password, suggest_portal_username
from .models import ClientPortalAccess


class PracticeContextMixin(LoginRequiredMixin, ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['practice'] = practice
        context['portal_clients'] = practice.clients.all() if practice else []
        context['portal_client_suggestions'] = [
            {
                'client': client,
                'username': suggest_portal_username(client),
                'email': client.email,
                'password': suggest_portal_password(),
            }
            for client in context['portal_clients']
        ]
        return context


class ClientPortalAccessMixin(LoginRequiredMixin):
    def get_portal_access(self):
        access = getattr(self.request.user, 'client_portal_access', None)
        if not access or not access.is_active:
            raise PermissionDenied('This account does not have active client portal access.')
        return access

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        access = self.get_portal_access()
        context['portal_access'] = access
        context['portal_client'] = access.client
        context['portal_practice'] = access.practice
        return context


class ClientPortalDashboardView(ClientPortalAccessMixin, TemplateView):
    template_name = 'portal/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        access = context['portal_access']
        now = timezone.now()
        context.update({
            'upcoming_appointments': Appointment.objects.filter(
                practice=access.practice,
                client=access.client,
                starts_at__gte=now,
            ).select_related('therapist__user')[:6],
            'visible_documents': ClientDocument.objects.filter(
                practice=access.practice,
                client=access.client,
                visible_to_client=True,
            )[:8],
            'open_invoices': Invoice.objects.filter(
                practice=access.practice,
                client=access.client,
            ).exclude(status__in=[Invoice.Status.PAID, Invoice.Status.VOID])[:8],
            'service_packages': ServicePackage.objects.filter(
                practice=access.practice,
                client=access.client,
            )[:6],
        })
        return context


class PortalAccessListView(PracticeContextMixin, ListView):
    model = ClientPortalAccess
    template_name = 'settings/portal_access.html'
    context_object_name = 'portal_accesses'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalAccess.objects.none()
        return ClientPortalAccess.objects.filter(practice=practice).select_related('client', 'user')


class PortalAccessCreateView(PracticeContextMixin, CreateView):
    model = ClientPortalAccess
    form_class = ClientPortalAccessForm
    template_name = 'settings/portal_access_form.html'
    success_url = reverse_lazy('portal_settings:portal_access')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def form_valid(self, form):
        action = AuditLog.Action.UPDATE if self.object else AuditLog.Action.CREATE
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            action,
            'portal.ClientPortalAccess',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'portal_user_id': self.object.user_id, 'is_active': self.object.is_active},
        )
        return response


class PortalAccessUpdateView(PortalAccessCreateView, UpdateView):
    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalAccess.objects.none()
        return ClientPortalAccess.objects.filter(practice=practice)


class PortalAccessDeleteView(PracticeContextMixin, DeleteView):
    model = ClientPortalAccess
    success_url = reverse_lazy('portal_settings:portal_access')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalAccess.objects.none()
        return ClientPortalAccess.objects.filter(practice=practice)

    def form_valid(self, form):
        access_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'portal_user_id': self.object.user_id, 'is_active': self.object.is_active}
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.DELETE, 'portal.ClientPortalAccess', access_id, practice=practice, metadata=metadata)
        return response
