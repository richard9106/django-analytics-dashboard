from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
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


class PackageCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = ServicePackage
    form_class = ServicePackageForm
    template_name = 'billing/package_form.html'
    success_url = reverse_lazy('billing:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs


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


class PackageUsageCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = PackageUsage
    form_class = PackageUsageForm
    template_name = 'billing/usage_form.html'
    success_url = reverse_lazy('billing:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs


class PackageUsageDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = PackageUsage
    success_url = reverse_lazy('billing:list')

    def get_queryset(self):
        practice = self.get_practice()
        return PackageUsage.objects.filter(package__practice=practice) if practice else PackageUsage.objects.none()


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
