from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from apps.appointments.models import Appointment
from apps.billing.models import Invoice, ServicePackage
from apps.documents.models import ClientDocument
from .forms import ClientPortalAccessForm, suggest_portal_password, suggest_portal_username
from .models import ClientPortalAccess


class PracticeContextMixin(LoginRequiredMixin):
    def get_practice(self):
        user = self.request.user
        user_profile = getattr(user, 'nuvia_profile', None)
        if user_profile:
            return user_profile.practice
        therapist_profile = getattr(user, 'therapist_profile', None)
        if therapist_profile:
            return therapist_profile.practice
        return None

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
