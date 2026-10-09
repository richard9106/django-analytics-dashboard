from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.db.models import Sum
from decimal import Decimal
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, PracticePermissionMixin, get_practice_for_user, has_practice_permission
from apps.clinical.forms import DiagnosisForm
from apps.appointments.models import Appointment
from apps.billing.models import Invoice, ServicePackage
from apps.clinical.models import Diagnosis, SessionNote, TreatmentPlan
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
        permissions = {resource: has_practice_permission(self.request.user, resource, 'view')
                       for resource in ('appointments', 'clinical', 'billing', 'documents', 'intake')}
        allowed_tabs = {'overview'} | {tab for tab in ('clinical', 'billing', 'documents') if permissions[tab]}
        requested_tab = self.request.GET.get('tab', 'overview')
        if self.request.method == 'POST' and self.request.POST.get('return_to_patient') == '1':
            requested_tab = 'clinical'
        active_tab = requested_tab if requested_tab in allowed_tabs else 'overview'
        context.update({
            'breadcrumbs': [{'label': 'Clients', 'url': reverse('clients:list')}, {'label': str(client)}],
            'workspace_tab': active_tab,
        })
        if has_practice_permission(self.request.user, 'clients', 'edit'):
            context['client_therapists'] = client.practice.therapists.select_related('user')
        if permissions['appointments']:
            appointments = Appointment.objects.filter(client=client, practice=client.practice).select_related('therapist__user')
            now = timezone.now()
            context['recent_appointments'] = appointments.filter(starts_at__lt=now).order_by('-starts_at')[:8]
            context['upcoming_appointments'] = appointments.filter(starts_at__gte=now, status=Appointment.Status.SCHEDULED).order_by('starts_at')[:5]
        if permissions['intake']:
            context['portal_access'] = ClientPortalAccess.objects.filter(client=client, practice=client.practice).first()
        if active_tab == 'billing':
            invoices = list(Invoice.objects.filter(client=client, practice=client.practice).annotate(
                workspace_paid=Sum('payments__amount'),
            ).order_by('-created_at')[:20])
            for invoice in invoices:
                invoice.workspace_balance = max(invoice.amount - (invoice.workspace_paid or Decimal('0.00')), Decimal('0.00'))
            context['invoices'] = invoices
            context['packages'] = ServicePackage.objects.filter(client=client, practice=client.practice).order_by('-created_at')[:8]
        if active_tab == 'documents':
            context['documents'] = ClientDocument.objects.filter(client=client, practice=client.practice).order_by('-created_at')[:20]
        if active_tab == 'clinical':
            context['notes'] = SessionNote.objects.filter(client=client, practice=client.practice).select_related('therapist__user', 'treatment_plan').order_by('-updated_at')[:8]
            context['treatment_plans'] = TreatmentPlan.objects.filter(client=client, practice=client.practice).prefetch_related('diagnoses').order_by('-updated_at')[:8]
            diagnoses = list(Diagnosis.objects.filter(client=client, practice=client.practice))
            context['diagnoses'] = diagnoses
            if has_practice_permission(self.request.user, 'clinical', 'create'):
                context['diagnosis_create_form'] = DiagnosisForm(practice=client.practice, patient=client, auto_id='diagnosis-create-%s')
            if has_practice_permission(self.request.user, 'clinical', 'edit'):
                context['diagnosis_edit_forms'] = [
                    (diagnosis, DiagnosisForm(instance=diagnosis, practice=client.practice,
                        patient=client, auto_id=f'diagnosis-edit-{diagnosis.pk}-%s'))
                    for diagnosis in diagnoses
                ]
        return context


class ClientCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'clients'
    permission_action = 'create'
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

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
