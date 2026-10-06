from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, PracticePermissionMixin, get_practice_for_user
from apps.practices.models import ExternalIntegration
from apps.appointments.models import Appointment
from apps.billing.models import Invoice, ServicePackage
from apps.clinical.models import SessionNote, TreatmentPlan
from apps.documents.models import ClientDocument
from apps.portal.models import ClientPortalAccess
from .forms import ClientForm
from .models import Client


class PracticeContextMixin(ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['practice'] = self.get_practice()
        return context


class ClientListView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'clients'
    model = Client
    template_name = 'clients/list.html'
    context_object_name = 'clients'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()

        return (
            Client.objects.filter(practice=practice)
            .select_related('primary_therapist__user')
            .order_by('last_name', 'first_name')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['client_therapists'] = practice.therapists.select_related('user') if practice else []
        context['note_appointments'] = practice.appointments.select_related('client', 'therapist__user') if practice else []
        context['billing_templates'] = practice.session_package_templates.filter(active=True) if practice else []
        context['billing_today'] = timezone.localdate()
        return context


class ClientDetailView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DetailView):
    permission_resource = 'clients'
    model = Client
    template_name = 'clients/detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()
        return Client.objects.filter(practice=practice).select_related('primary_therapist__user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.object
        now = timezone.now()
        context.update({
            'breadcrumbs': [
                {'label': 'Clients', 'url': reverse('clients:list')},
                {'label': str(client)},
            ],
            'client_therapists': client.practice.therapists.select_related('user'),
            'upcoming_appointments': Appointment.objects.filter(client=client, starts_at__gte=now).select_related('therapist__user')[:8],
            'recent_appointments': Appointment.objects.filter(client=client, starts_at__lt=now).select_related('therapist__user').order_by('-starts_at')[:8],
            'invoices': Invoice.objects.filter(client=client).order_by('-created_at')[:8],
            'packages': ServicePackage.objects.filter(client=client).order_by('-created_at')[:8],
            'notes': SessionNote.objects.filter(client=client).select_related('therapist__user', 'treatment_plan')[:8],
            'treatment_plans': TreatmentPlan.objects.filter(client=client).prefetch_related('diagnoses')[:8],
            'documents': ClientDocument.objects.filter(client=client).order_by('-created_at')[:8],
            'portal_access': ClientPortalAccess.objects.filter(client=client).first(),
        })
        return context


class ClientCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'clients'
    permission_action = 'create'
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

    def dispatch(self, request, *args, **kwargs):
        practice = self.get_practice()
        gmail_ready = ExternalIntegration.objects.filter(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            send_email_enabled=True,
        ).exists() if practice else False
        if request.user.is_authenticated and practice and not (practice.can_receive_client_payments and gmail_ready):
            messages.warning(request, 'Complete Gmail and Stripe Connect setup before adding clients.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Client'
        context['form_heading'] = 'Create a client profile'
        context['submit_label'] = 'Create client'
        return context


class ClientUpdateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, UpdateView):
    permission_resource = 'clients'
    permission_action = 'edit'
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()

        return Client.objects.filter(practice=practice)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Client'
        context['form_heading'] = 'Edit client profile'
        context['submit_label'] = 'Save changes'
        context['show_delete_action'] = True
        return context


class ClientDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'clients'
    permission_action = 'delete'
    model = Client
    success_url = reverse_lazy('clients:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()

        return Client.objects.filter(practice=practice)

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            self.request._audit_denied_reason = 'clinical_record_retained'
            messages.error(self.request, 'This client has clinical records and must be retained. Archive the client instead.')
            return redirect('clients:detail', pk=self.object.pk)
