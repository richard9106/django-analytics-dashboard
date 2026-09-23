from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .forms import InvoiceForm, PackageUsageForm, ServicePackageForm, SessionPackageTemplateForm
from .models import Invoice, PackageUsage, ServicePackage, SessionPackageTemplate


class PracticeContextMixin(ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['practice'] = practice
        if practice:
            context['billing_clients'] = practice.clients.all()
            context['billing_appointments'] = practice.appointments.select_related('client')
            context['billing_packages'] = practice.service_packages.select_related('client')
            context['billing_templates'] = practice.session_package_templates.filter(active=True)
        else:
            context['billing_clients'] = []
            context['billing_appointments'] = []
            context['billing_packages'] = []
            context['billing_templates'] = []
        return context


class BillingListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = Invoice
    template_name = 'billing/list.html'
    context_object_name = 'invoices'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Invoice.objects.none()
        return Invoice.objects.filter(practice=practice).select_related('client', 'appointment', 'package')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['packages'] = (
            ServicePackage.objects.filter(practice=practice).select_related('client') if practice else ServicePackage.objects.none()
        )
        context['package_usages'] = (
            PackageUsage.objects.filter(package__practice=practice).select_related('package__client', 'appointment') if practice else PackageUsage.objects.none()
        )
        return context


class InvoiceCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'billing/invoice_form.html'
    success_url = reverse_lazy('billing:list')

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
            'billing.Invoice',
            self.object.pk,
            practice=self.object.practice,
            metadata={
                'client_id': self.object.client_id,
                'appointment_id': self.object.appointment_id,
                'package_id': self.object.package_id,
                'invoice_number': self.object.invoice_number,
                'status': self.object.status,
            },
        )
        return response


class InvoiceUpdateView(InvoiceCreateView, UpdateView):
    def get_queryset(self):
        practice = self.get_practice()
        return Invoice.objects.filter(practice=practice) if practice else Invoice.objects.none()


class InvoiceDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = Invoice
    success_url = reverse_lazy('billing:list')

    def get_queryset(self):
        practice = self.get_practice()
        return Invoice.objects.filter(practice=practice) if practice else Invoice.objects.none()

    def form_valid(self, form):
        invoice_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'invoice_number': self.object.invoice_number, 'status': self.object.status}
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.DELETE, 'billing.Invoice', invoice_id, practice=practice, metadata=metadata)
        return response


class PackageCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = ServicePackage
    form_class = ServicePackageForm
    template_name = 'billing/package_form.html'
    success_url = reverse_lazy('billing:list')

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
            'billing.ServicePackage',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'status': self.object.status, 'sessions_remaining': self.object.sessions_remaining},
        )
        return response


class PackageUpdateView(PackageCreateView, UpdateView):
    def get_queryset(self):
        practice = self.get_practice()
        return ServicePackage.objects.filter(practice=practice) if practice else ServicePackage.objects.none()


class PackageDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = ServicePackage
    success_url = reverse_lazy('billing:list')

    def get_queryset(self):
        practice = self.get_practice()
        return ServicePackage.objects.filter(practice=practice) if practice else ServicePackage.objects.none()

    def form_valid(self, form):
        package_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'status': self.object.status}
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.DELETE, 'billing.ServicePackage', package_id, practice=practice, metadata=metadata)
        return response


class PackageUsageCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = PackageUsage
    form_class = PackageUsageForm
    template_name = 'billing/usage_form.html'
    success_url = reverse_lazy('billing:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            'billing.PackageUsage',
            self.object.pk,
            practice=self.object.package.practice,
            metadata={'package_id': self.object.package_id, 'appointment_id': self.object.appointment_id, 'quantity': self.object.quantity},
        )
        return response


class PackageUsageDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = PackageUsage
    success_url = reverse_lazy('billing:list')

    def get_queryset(self):
        practice = self.get_practice()
        return PackageUsage.objects.filter(package__practice=practice) if practice else PackageUsage.objects.none()

    def form_valid(self, form):
        usage_id = self.object.pk
        practice = self.object.package.practice
        metadata = {'package_id': self.object.package_id, 'appointment_id': self.object.appointment_id, 'quantity': self.object.quantity}
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.DELETE, 'billing.PackageUsage', usage_id, practice=practice, metadata=metadata)
        return response


class SessionPackageTemplateListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = SessionPackageTemplate
    template_name = 'settings/package_templates.html'
    context_object_name = 'templates'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionPackageTemplate.objects.none()
        return SessionPackageTemplate.objects.filter(practice=practice)


class SessionPackageTemplateCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = SessionPackageTemplate
    form_class = SessionPackageTemplateForm
    template_name = 'settings/package_template_form.html'
    success_url = reverse_lazy('settings:package_templates')

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
            'billing.SessionPackageTemplate',
            self.object.pk,
            practice=self.object.practice,
            metadata={'name': self.object.name, 'sessions_included': self.object.sessions_included, 'active': self.object.active},
        )
        return response


class SessionPackageTemplateUpdateView(SessionPackageTemplateCreateView, UpdateView):
    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionPackageTemplate.objects.none()
        return SessionPackageTemplate.objects.filter(practice=practice)


class SessionPackageTemplateDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = SessionPackageTemplate
    success_url = reverse_lazy('settings:package_templates')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionPackageTemplate.objects.none()
        return SessionPackageTemplate.objects.filter(practice=practice)

    def form_valid(self, form):
        template_id = self.object.pk
        practice = self.object.practice
        metadata = {'name': self.object.name, 'active': self.object.active}
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.DELETE, 'billing.SessionPackageTemplate', template_id, practice=practice, metadata=metadata)
        return response
