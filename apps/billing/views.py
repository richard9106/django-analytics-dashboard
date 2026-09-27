from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .forms import InsurancePayerForm, InsuranceRateForm, InvoiceForm, PackageUsageForm, ServicePackageForm, SessionPackageTemplateForm
from .models import InsurancePayer, InsuranceRate, Invoice, PackageUsage, PracticeSubscription, ServicePackage, SessionPackageTemplate


def _stripe_price_id(plan, period):
    return settings.STRIPE_PRICE_IDS.get(plan, {}).get(period, '')


def _plan_period_for_price(price_id):
    for plan, periods in settings.STRIPE_PRICE_IDS.items():
        for period, configured_price_id in periods.items():
            if configured_price_id and configured_price_id == price_id:
                return plan, period
    return '', ''


def _period_end_from_subscription(stripe_subscription):
    period_end = stripe_subscription.get('current_period_end')
    if not period_end:
        return None
    return datetime.fromtimestamp(period_end, tz=dt_timezone.utc)


def _sync_subscription_from_stripe(stripe_subscription, practice=None):
    price_id = ''
    items = stripe_subscription.get('items', {}).get('data', [])
    if items:
        price_id = items[0].get('price', {}).get('id', '')
    plan, period = _plan_period_for_price(price_id)

    if practice is None:
        metadata = stripe_subscription.get('metadata', {}) or {}
        practice_id = metadata.get('practice_id')
        if practice_id:
            from apps.practices.models import Practice

            practice = Practice.objects.filter(pk=practice_id).first()

    if practice is None:
        existing = PracticeSubscription.objects.filter(stripe_subscription_id=stripe_subscription.get('id', '')).first()
        practice = existing.practice if existing else None

    if practice is None:
        return None

    defaults = {
        'status': stripe_subscription.get('status', PracticeSubscription.Status.INCOMPLETE),
        'stripe_customer_id': stripe_subscription.get('customer', ''),
        'stripe_subscription_id': stripe_subscription.get('id', ''),
        'stripe_price_id': price_id,
        'current_period_end': _period_end_from_subscription(stripe_subscription),
    }
    if plan:
        defaults['plan'] = plan
    if period:
        defaults['billing_period'] = period

    subscription, _ = PracticeSubscription.objects.update_or_create(
        practice=practice,
        defaults=defaults,
    )
    return subscription


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


class InvoicePrintableView(LoginRequiredMixin, PracticeContextMixin, TemplateView):
    template_name = 'billing/printable_invoice.html'
    document_type = 'invoice'

    def get_invoice(self):
        practice = self.get_practice()
        return get_object_or_404(
            Invoice.objects.filter(practice=practice).select_related('practice', 'client', 'appointment__therapist__user', 'package'),
            pk=self.kwargs['pk'],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_invoice()
        context['invoice'] = invoice
        context['document_type'] = self.document_type
        context['is_superbill'] = self.document_type == 'superbill'
        log_audit_event(
            self.request,
            AuditLog.Action.EXPORT,
            'billing.Invoice',
            invoice.pk,
            practice=invoice.practice,
            metadata={'invoice_number': invoice.invoice_number, 'document_type': self.document_type},
        )
        return context


class InvoiceSuperbillView(InvoicePrintableView):
    document_type = 'superbill'


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


class InsuranceSettingsView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = InsuranceRate
    template_name = 'settings/insurance.html'
    context_object_name = 'insurance_rates'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return InsuranceRate.objects.none()
        return InsuranceRate.objects.filter(practice=practice).select_related('payer')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['system_payers'] = InsurancePayer.objects.filter(practice__isnull=True, active=True)
        context['custom_payers'] = InsurancePayer.objects.filter(practice=practice) if practice else InsurancePayer.objects.none()
        context['payer_form'] = InsurancePayerForm(practice=practice)
        context['rate_form'] = InsuranceRateForm(practice=practice)
        return context


class InsurancePayerCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = InsurancePayer
    form_class = InsurancePayerForm
    template_name = 'settings/insurance_payer_form.html'
    success_url = reverse_lazy('settings:insurance')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def form_valid(self, form):
        action = AuditLog.Action.UPDATE if self.object else AuditLog.Action.CREATE
        response = super().form_valid(form)
        log_audit_event(self.request, action, 'billing.InsurancePayer', self.object.pk, practice=self.object.practice, metadata={'name': self.object.name})
        return response


class InsurancePayerUpdateView(InsurancePayerCreateView, UpdateView):
    def get_queryset(self):
        practice = self.get_practice()
        return InsurancePayer.objects.filter(practice=practice) if practice else InsurancePayer.objects.none()


class InsurancePayerDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = InsurancePayer
    success_url = reverse_lazy('settings:insurance')

    def get_queryset(self):
        practice = self.get_practice()
        return InsurancePayer.objects.filter(practice=practice) if practice else InsurancePayer.objects.none()


class InsuranceRateCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = InsuranceRate
    form_class = InsuranceRateForm
    template_name = 'settings/insurance_rate_form.html'
    success_url = reverse_lazy('settings:insurance')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def form_valid(self, form):
        action = AuditLog.Action.UPDATE if self.object else AuditLog.Action.CREATE
        response = super().form_valid(form)
        log_audit_event(self.request, action, 'billing.InsuranceRate', self.object.pk, practice=self.object.practice, metadata={'payer_id': self.object.payer_id, 'state': self.object.state, 'service_code': self.object.service_code})
        return response


class InsuranceRateUpdateView(InsuranceRateCreateView, UpdateView):
    def get_queryset(self):
        practice = self.get_practice()
        return InsuranceRate.objects.filter(practice=practice) if practice else InsuranceRate.objects.none()


class InsuranceRateDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = InsuranceRate
    success_url = reverse_lazy('settings:insurance')

    def get_queryset(self):
        practice = self.get_practice()
        return InsuranceRate.objects.filter(practice=practice) if practice else InsuranceRate.objects.none()


class StripeSubscribeView(LoginRequiredMixin, ClientPortalRedirectMixin, View):
    http_method_names = ['get', 'post']

    def dispatch(self, request, *args, **kwargs):
        self.plan = kwargs.get('plan')
        self.period = kwargs.get('period')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.create_checkout_session(request)

    def post(self, request, *args, **kwargs):
        return self.create_checkout_session(request)

    def create_checkout_session(self, request):
        practice = get_practice_for_user(request.user)
        price_id = _stripe_price_id(self.plan, self.period)
        if self.plan not in PracticeSubscription.Plan.values or self.period not in PracticeSubscription.BillingPeriod.values:
            return HttpResponseBadRequest('Unknown subscription plan.')
        if not practice:
            messages.error(request, 'Create a practice workspace before starting a subscription.')
            return redirect('signup')
        if not settings.STRIPE_SECRET_KEY or not price_id:
            messages.error(request, 'Online subscription checkout is not configured yet. Please contact NuviaMy support.')
            return redirect('pricing')

        stripe.api_key = settings.STRIPE_SECRET_KEY
        subscription = getattr(practice, 'subscription', None)
        customer_id = subscription.stripe_customer_id if subscription else ''
        session_kwargs = {
            'mode': 'subscription',
            'line_items': [{'price': price_id, 'quantity': 1}],
            'success_url': request.build_absolute_uri(reverse('billing:subscribe_success')) + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': request.build_absolute_uri(reverse('billing:subscribe_cancel')),
            'client_reference_id': str(practice.pk),
            'metadata': {'practice_id': str(practice.pk), 'plan': self.plan, 'period': self.period},
            'subscription_data': {'metadata': {'practice_id': str(practice.pk), 'plan': self.plan, 'period': self.period}},
        }
        if customer_id:
            session_kwargs['customer'] = customer_id
        else:
            session_kwargs['customer_email'] = request.user.email

        session = stripe.checkout.Session.create(**session_kwargs)
        PracticeSubscription.objects.update_or_create(
            practice=practice,
            defaults={
                'plan': self.plan,
                'billing_period': self.period,
                'status': PracticeSubscription.Status.INCOMPLETE,
                'stripe_customer_id': customer_id,
                'stripe_price_id': price_id,
            },
        )
        return redirect(session.url)


class StripeSubscribeSuccessView(LoginRequiredMixin, ClientPortalRedirectMixin, TemplateView):
    template_name = 'billing/subscribe_success.html'


class StripeSubscribeCancelView(LoginRequiredMixin, ClientPortalRedirectMixin, TemplateView):
    template_name = 'billing/subscribe_cancel.html'


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return HttpResponseBadRequest('Webhook not configured.')

        signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        try:
            event = stripe.Webhook.construct_event(request.body, signature, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponseBadRequest('Invalid Stripe webhook payload.')

        event_type = event.get('type')
        data_object = event.get('data', {}).get('object', {})
        if event_type == 'checkout.session.completed':
            subscription_id = data_object.get('subscription')
            if subscription_id:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                _sync_subscription_from_stripe(stripe_subscription)
        elif event_type in {'customer.subscription.updated', 'customer.subscription.deleted'}:
            _sync_subscription_from_stripe(data_object)
        elif event_type == 'invoice.payment_failed':
            subscription_id = data_object.get('subscription')
            if subscription_id:
                PracticeSubscription.objects.filter(stripe_subscription_id=subscription_id).update(status=PracticeSubscription.Status.PAST_DUE)

        return HttpResponse(status=200)
