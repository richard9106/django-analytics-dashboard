from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, PracticePermissionMixin, get_practice_for_user
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .forms import InsurancePayerForm, InsuranceRateForm, InvoiceForm, PackageUsageForm, PaymentForm, ServicePackageForm, SessionPackageTemplateForm
from .models import InsurancePayer, InsuranceRate, Invoice, PackageUsage, Payment, PracticeSubscription, ServicePackage, SessionPackageTemplate


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


def _format_stripe_amount(amount, currency='usd'):
    amount = amount or 0
    return f"{currency.upper()} {amount / 100:,.2f}"


def _subscription_item_id(stripe_subscription):
    items = stripe_subscription.get('items', {}).get('data', [])
    return items[0].get('id', '') if items else ''


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


class BillingListView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'billing'
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
        context['payment_form'] = PaymentForm(practice=practice)
        return context


class PaymentCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
    model = Payment
    form_class = PaymentForm
    template_name = 'billing/payment_form.html'
    success_url = reverse_lazy('billing:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        invoice = self.object.invoice
        if invoice.balance_due <= 0:
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = self.object.paid_at
            invoice.save(update_fields=['status', 'paid_at', 'updated_at'])
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            'billing.Payment',
            self.object.pk,
            practice=self.object.practice,
            metadata={'invoice_id': invoice.pk, 'amount': str(self.object.amount), 'method': self.object.method},
        )
        return response


class InvoiceCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
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
    permission_action = 'edit'
    def get_queryset(self):
        practice = self.get_practice()
        return Invoice.objects.filter(practice=practice, status=Invoice.Status.DRAFT) if practice else Invoice.objects.none()


class InvoiceDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'billing'
    permission_action = 'delete'
    model = Invoice
    success_url = reverse_lazy('billing:list')

    def get_queryset(self):
        practice = self.get_practice()
        return Invoice.objects.filter(practice=practice, status=Invoice.Status.DRAFT) if practice else Invoice.objects.none()

    def form_valid(self, form):
        invoice_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'invoice_number': self.object.invoice_number, 'status': self.object.status}
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.DELETE, 'billing.Invoice', invoice_id, practice=practice, metadata=metadata)
        return response


class InvoicePublishView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'billing'
    permission_action = 'edit'
    http_method_names = ['post']

    def post(self, request, pk):
        practice = self.get_practice()
        invoice = get_object_or_404(Invoice, pk=pk, practice=practice, status=Invoice.Status.DRAFT)
        invoice.status = Invoice.Status.SENT
        invoice.published_at = timezone.now()
        invoice.published_by = request.user
        invoice.save(update_fields=['status', 'published_at', 'published_by', 'updated_at'])
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'billing.Invoice',
            invoice.pk,
            practice=practice,
            metadata={'event': 'published', 'invoice_number': invoice.invoice_number, 'status': invoice.status},
        )
        messages.success(request, f'Invoice {invoice.invoice_number} published.')
        return redirect('billing:list')


class InvoicePrintableView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, TemplateView):
    permission_resource = 'billing'
    permission_action = 'view'
    template_name = 'billing/printable_invoice.html'
    document_type = 'invoice'

    def get_invoice(self):
        practice = self.get_practice()
        return get_object_or_404(
            Invoice.objects.filter(practice=practice).select_related('practice', 'client', 'appointment__therapist__user', 'package', 'published_by').prefetch_related('payments'),
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


class PackageCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
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
    permission_action = 'edit'
    def get_queryset(self):
        practice = self.get_practice()
        return ServicePackage.objects.filter(practice=practice) if practice else ServicePackage.objects.none()


class PackageDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'billing'
    permission_action = 'delete'
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


class PackageUsageCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
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


class PackageUsageDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'billing'
    permission_action = 'delete'
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


class SessionPackageTemplateListView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'billing'
    permission_action = 'view'
    model = SessionPackageTemplate
    template_name = 'settings/package_templates.html'
    context_object_name = 'templates'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionPackageTemplate.objects.none()
        return SessionPackageTemplate.objects.filter(practice=practice)


class SessionPackageTemplateCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
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
    permission_action = 'edit'
    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionPackageTemplate.objects.none()
        return SessionPackageTemplate.objects.filter(practice=practice)


class SessionPackageTemplateDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'billing'
    permission_action = 'delete'
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


class InsuranceSettingsView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'billing'
    permission_action = 'view'
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


class InsurancePayerCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
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
    permission_action = 'edit'
    def get_queryset(self):
        practice = self.get_practice()
        return InsurancePayer.objects.filter(practice=practice) if practice else InsurancePayer.objects.none()


class InsurancePayerDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'billing'
    permission_action = 'delete'
    model = InsurancePayer
    success_url = reverse_lazy('settings:insurance')

    def get_queryset(self):
        practice = self.get_practice()
        return InsurancePayer.objects.filter(practice=practice) if practice else InsurancePayer.objects.none()


class InsuranceRateCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'billing'
    permission_action = 'create'
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
    permission_action = 'edit'
    def get_queryset(self):
        practice = self.get_practice()
        return InsuranceRate.objects.filter(practice=practice) if practice else InsuranceRate.objects.none()


class InsuranceRateDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'billing'
    permission_action = 'delete'
    model = InsuranceRate
    success_url = reverse_lazy('settings:insurance')

    def get_queryset(self):
        practice = self.get_practice()
        return InsuranceRate.objects.filter(practice=practice) if practice else InsuranceRate.objects.none()


class StripeSubscribeView(LoginRequiredMixin, PracticePermissionMixin, ClientPortalRedirectMixin, View):
    permission_resource = 'billing'
    permission_action = 'create'
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
            'payment_method_collection': 'always',
            'line_items': [{'price': price_id, 'quantity': 1}],
            'success_url': request.build_absolute_uri(reverse('billing:subscribe_success')) + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': request.build_absolute_uri(reverse('billing:subscribe_cancel')),
            'client_reference_id': str(practice.pk),
            'metadata': {'practice_id': str(practice.pk), 'plan': self.plan, 'period': self.period},
            'subscription_data': {
                'metadata': {'practice_id': str(practice.pk), 'plan': self.plan, 'period': self.period},
                'trial_period_days': 15,
            },
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


class StripeSubscribeSuccessView(LoginRequiredMixin, PracticePermissionMixin, ClientPortalRedirectMixin, TemplateView):
    permission_resource = 'billing'
    permission_action = 'view'
    template_name = 'billing/subscribe_success.html'


class StripeSubscribeCancelView(LoginRequiredMixin, PracticePermissionMixin, ClientPortalRedirectMixin, TemplateView):
    permission_resource = 'billing'
    permission_action = 'view'
    template_name = 'billing/subscribe_cancel.html'


class StripeCustomerPortalView(LoginRequiredMixin, PracticePermissionMixin, ClientPortalRedirectMixin, View):
    permission_resource = 'billing'
    permission_action = 'edit'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        practice = get_practice_for_user(request.user)
        subscription = getattr(practice, 'subscription', None) if practice else None
        if not settings.STRIPE_SECRET_KEY or not subscription or not subscription.stripe_customer_id:
            messages.error(request, 'Stripe billing management is not available for this account yet.')
            return redirect('profile_settings')

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=request.build_absolute_uri(reverse('profile_settings')),
            )
        except stripe.error.StripeError:
            messages.error(request, 'Stripe could not open billing management. Please try again later.')
            return redirect('profile_settings')
        return redirect(session.url)


class StripeChangePlanView(LoginRequiredMixin, PracticePermissionMixin, ClientPortalRedirectMixin, View):
    permission_resource = 'billing'
    permission_action = 'edit'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        plan = kwargs.get('plan')
        period = kwargs.get('period')
        practice = get_practice_for_user(request.user)
        price_id = _stripe_price_id(plan, period)
        if plan not in PracticeSubscription.Plan.values or period not in PracticeSubscription.BillingPeriod.values:
            return HttpResponseBadRequest('Unknown subscription plan.')
        if not practice:
            messages.error(request, 'Create a practice workspace before changing plans.')
            return redirect('signup')

        internal_user_count = practice.user_profiles.exclude(role__in=['client', 'owner']).count()
        target_limit = PracticeSubscription.internal_user_limit_for_plan(plan)
        if internal_user_count > target_limit:
            messages.error(
                request,
                f'This practice has {internal_user_count} internal users. The {PracticeSubscription.Plan(plan).label} plan allows up to {target_limit}.',
            )
            return redirect('profile_settings')

        subscription = getattr(practice, 'subscription', None)
        if not subscription or not subscription.stripe_subscription_id:
            return redirect('billing:subscribe', plan=plan, period=period)
        if subscription.plan == plan and subscription.billing_period == period:
            messages.info(request, 'That plan is already active for this practice.')
            return redirect('profile_settings')
        if not settings.STRIPE_SECRET_KEY or not price_id:
            messages.error(request, 'Online subscription changes are not configured yet. Please contact NuviaMy support.')
            return redirect('profile_settings')

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            items = stripe_subscription.get('items', {}).get('data', [])
            if not items:
                messages.error(request, 'Stripe could not find the active subscription item. Please contact NuviaMy support.')
                return redirect('profile_settings')
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{'id': items[0]['id'], 'price': price_id}],
                proration_behavior='create_prorations',
                metadata={'practice_id': str(practice.pk), 'plan': plan, 'period': period},
            )
        except stripe.error.StripeError:
            messages.error(request, 'Stripe could not change your plan. Please try again later.')
            return redirect('profile_settings')

        subscription.plan = plan
        subscription.billing_period = period
        subscription.stripe_price_id = price_id
        subscription.save(update_fields=['plan', 'billing_period', 'stripe_price_id', 'updated_at'])
        messages.success(request, f'Plan changed to {PracticeSubscription.Plan(plan).label}.')
        return redirect('profile_settings')


class StripePlanPreviewView(LoginRequiredMixin, PracticePermissionMixin, ClientPortalRedirectMixin, View):
    permission_resource = 'billing'
    permission_action = 'view'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        plan = kwargs.get('plan')
        period = kwargs.get('period')
        practice = get_practice_for_user(request.user)
        price_id = _stripe_price_id(plan, period)
        if plan not in PracticeSubscription.Plan.values or period not in PracticeSubscription.BillingPeriod.values:
            return JsonResponse({'error': 'Unknown subscription plan.'}, status=400)
        if not practice:
            return JsonResponse({'error': 'Create a practice workspace before changing plans.'}, status=400)

        internal_user_count = practice.user_profiles.exclude(role__in=['client', 'owner']).count()
        target_limit = PracticeSubscription.internal_user_limit_for_plan(plan)
        if internal_user_count > target_limit:
            return JsonResponse({
                'error': (
                    f'This practice has {internal_user_count} internal users. '
                    f'The {PracticeSubscription.Plan(plan).label} plan allows up to {target_limit}.'
                )
            }, status=400)

        subscription = getattr(practice, 'subscription', None)
        if not subscription or not subscription.stripe_subscription_id:
            return JsonResponse({
                'summary': 'Stripe Checkout will show the first subscription invoice before payment.',
                'amount_due': '',
                'subtotal': '',
                'credit': '',
                'currency': 'USD',
            })
        if not settings.STRIPE_SECRET_KEY or not price_id:
            return JsonResponse({'error': 'Online subscription previews are not configured yet.'}, status=400)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            item_id = _subscription_item_id(stripe_subscription)
            if not item_id:
                return JsonResponse({'error': 'Stripe could not find the active subscription item.'}, status=400)
            preview = stripe.Invoice.create_preview(
                customer=subscription.stripe_customer_id,
                subscription=subscription.stripe_subscription_id,
                subscription_details={
                    'items': [{'id': item_id, 'price': price_id}],
                    'proration_behavior': 'create_prorations',
                },
            )
        except stripe.error.StripeError:
            return JsonResponse({'error': 'Stripe could not preview this plan change. Please try again later.'}, status=400)

        currency = preview.get('currency', 'usd')
        subtotal = preview.get('subtotal', 0)
        amount_due = preview.get('amount_due', 0)
        credit = sum(line.get('amount', 0) for line in preview.get('lines', {}).get('data', []) if line.get('amount', 0) < 0)
        return JsonResponse({
            'summary': 'Stripe estimate based on your current billing period. Final taxes or payment timing may vary in Stripe.',
            'amount_due': _format_stripe_amount(amount_due, currency),
            'subtotal': _format_stripe_amount(subtotal, currency),
            'credit': _format_stripe_amount(abs(credit), currency) if credit else '',
            'currency': currency.upper(),
        })


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
        if event_type in {'checkout.session.completed', 'checkout.session.async_payment_succeeded'}:
            subscription_id = data_object.get('subscription')
            if subscription_id:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                _sync_subscription_from_stripe(stripe_subscription)
            invoice_id = (data_object.get('metadata') or {}).get('invoice_id')
            if invoice_id and data_object.get('payment_status', 'paid') == 'paid':
                Invoice.objects.filter(
                    pk=invoice_id,
                    practice_id=(data_object.get('metadata') or {}).get('practice_id'),
                    client_id=(data_object.get('metadata') or {}).get('client_id'),
                ).exclude(status=Invoice.Status.VOID).update(
                    status=Invoice.Status.PAID,
                    paid_at=timezone.now(),
                )
        elif event_type in {'customer.subscription.updated', 'customer.subscription.deleted'}:
            _sync_subscription_from_stripe(data_object)
        elif event_type == 'invoice.payment_failed':
            subscription_id = data_object.get('subscription')
            if subscription_id:
                PracticeSubscription.objects.filter(stripe_subscription_id=subscription_id).update(status=PracticeSubscription.Status.PAST_DUE)

        return HttpResponse(status=200)
