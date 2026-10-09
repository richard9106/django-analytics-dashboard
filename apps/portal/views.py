from datetime import datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import CharField, Count, Q, Sum, Value
from django.db.models.functions import Concat
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView
import stripe
from django.conf import settings

from apps.accounts.access import ClientPortalRedirectMixin, ForcePasswordChangeRequiredMixin, PracticePermissionMixin, get_practice_for_user, has_practice_permission, permission_redirect
from apps.accounts.models import UserProfile
from apps.appointments.google_calendar import sync_appointment_to_google
from apps.appointments.models import Appointment, practice_allows_interval
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.billing.models import Invoice, ServicePackage
from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.practices.models import Practice
from apps.rate_limit import PostRateLimitMixin
from .forms import (
    ClientIntakeAssignmentForm,
    ClientIntakeResponseForm,
    AppointmentChangeRequestForm,
    ClientPortalAccessForm,
    ClientPortalRequestForm,
    PortalConversationForm,
    PortalMessageForm,
    IntakePacketTemplateForm,
    PublicBookingRequestForm,
    suggest_portal_password,
    suggest_portal_username,
)
from .models import ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate, PortalConversation, PortalMessage, PublicBookingRequest


PUBLIC_BOOKING_SLOT_MINUTES = 50
PUBLIC_BOOKING_SLOT_STEP_MINUTES = 30


def public_booking_date_options(days=14):
    today = timezone.localdate()
    return [today + timedelta(days=offset) for offset in range(1, days + 1)]


def selected_public_booking_date(request):
    raw_value = request.POST.get('booking_date') or request.GET.get('date')
    options = public_booking_date_options()
    if raw_value:
        try:
            selected = datetime.strptime(raw_value, '%Y-%m-%d').date()
        except ValueError:
            selected = options[0]
        return selected if selected in options else options[0]
    return options[0]


def public_booking_slots(practice, selected_date):
    slots = []
    grid_start = timezone.make_aware(datetime.combine(selected_date, time(hour=7)))
    grid_end = timezone.make_aware(datetime.combine(selected_date, time(hour=20)))
    existing = list(Appointment.objects.filter(
        practice=practice,
        status=Appointment.Status.SCHEDULED,
        starts_at__lt=grid_end,
        ends_at__gt=grid_start,
    ).only('starts_at', 'ends_at'))
    cursor = grid_start
    while cursor + timedelta(minutes=PUBLIC_BOOKING_SLOT_MINUTES) <= grid_end:
        slot_end = cursor + timedelta(minutes=PUBLIC_BOOKING_SLOT_MINUTES)
        overlaps = any(appointment.starts_at < slot_end and appointment.ends_at > cursor for appointment in existing)
        if not overlaps and practice_allows_interval(practice, cursor, slot_end):
            local_start = timezone.localtime(cursor)
            slots.append({
                'value': local_start.strftime('%Y-%m-%dT%H:%M'),
                'label': f'{local_start:%-I:%M %p} - {timezone.localtime(slot_end):%-I:%M %p}',
            })
        cursor += timedelta(minutes=PUBLIC_BOOKING_SLOT_STEP_MINUTES)
    return slots


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


class ClientPortalAccessMixin(LoginRequiredMixin, ForcePasswordChangeRequiredMixin):
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
        upcoming_appointments = list(Appointment.objects.filter(
            practice=access.practice,
            client=access.client,
            starts_at__gte=now,
        ).select_related('therapist__user')[:6])
        for appointment in upcoming_appointments:
            appointment.change_request_form = AppointmentChangeRequestForm(
                portal_access=access, appointment=appointment,
            )
        open_invoices = Invoice.objects.filter(
            practice=access.practice,
            client=access.client,
            status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
        ).prefetch_related('payments')
        visible_documents = ClientDocument.objects.filter(
            practice=access.practice,
            client=access.client,
            visible_to_client=True,
        )
        service_packages = ServicePackage.objects.filter(
            practice=access.practice,
            client=access.client,
        )
        portal_requests = ClientPortalRequest.objects.filter(
            practice=access.practice,
            client=access.client,
        )
        pending_intakes = ClientIntakeAssignment.objects.filter(
            practice=access.practice,
            client=access.client,
            status=ClientIntakeAssignment.Status.ASSIGNED,
        ).select_related('template')
        unread_message_count = PortalMessage.objects.filter(
            practice=access.practice,
            conversation__client=access.client,
            author_kind=PortalMessage.AuthorKind.STAFF,
            read_at__isnull=True,
        ).count()
        context.update({
            'upcoming_appointments': upcoming_appointments,
            'next_appointment': upcoming_appointments[0] if upcoming_appointments else None,
            'visible_documents': visible_documents[:8],
            'open_invoices': open_invoices[:8],
            'open_invoice_total': sum(invoice.balance_due for invoice in open_invoices),
            'service_packages': service_packages[:6],
            'remaining_sessions': sum(package.sessions_remaining for package in service_packages),
            'shared_document_count': visible_documents.count(),
            'portal_request_form': ClientPortalRequestForm(portal_access=access),
            'portal_requests': portal_requests[:5],
            'open_request_count': portal_requests.exclude(status=ClientPortalRequest.Status.RESOLVED).count(),
            'pending_intakes': pending_intakes,
            'pending_intake_count': pending_intakes.count(),
            'unread_message_count': unread_message_count,
            'client_payments_ready': bool(settings.STRIPE_SECRET_KEY and access.practice.can_receive_client_payments),
        })
        return context


class ClientInvoicePaymentView(ClientPortalAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        access = self.get_portal_access()
        invoice = get_object_or_404(
            Invoice,
            pk=kwargs['pk'],
            practice=access.practice,
            client=access.client,
        )
        if invoice.status not in {Invoice.Status.SENT, Invoice.Status.OVERDUE} or invoice.balance_due <= 0:
            messages.error(request, 'This invoice is not available for online payment.')
            return redirect('portal:dashboard')
        if not settings.STRIPE_SECRET_KEY:
            messages.error(request, 'Online payments are not configured yet. Please contact the practice.')
            return redirect('portal:dashboard')
        if not access.practice.can_receive_client_payments:
            messages.error(request, 'The practice has not finished setting up client payments yet. Please contact the practice.')
            return redirect('portal:dashboard')

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.create(
                mode='payment',
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {'name': f'Invoice {invoice.invoice_number}'},
                         'unit_amount': int(invoice.balance_due * 100),
                    },
                    'quantity': 1,
                }],
                customer_email=access.client.email or None,
                payment_intent_data={
                    'transfer_data': {'destination': access.practice.stripe_connect_account_id},
                },
                success_url=request.build_absolute_uri(reverse('portal:dashboard')),
                cancel_url=request.build_absolute_uri(reverse('portal:dashboard')),
                metadata={
                    'invoice_id': str(invoice.pk),
                    'practice_id': str(invoice.practice_id),
                    'client_id': str(invoice.client_id),
                },
            )
        except stripe.error.StripeError:
            messages.error(request, 'Stripe could not open payment checkout. Please try again later.')
            return redirect('portal:dashboard')
        return redirect(session.url)


class ClientPortalRequestCreateView(ClientPortalAccessMixin, View):
    def get_portal_context(self, access, form):
        now = timezone.now()
        upcoming_appointments = Appointment.objects.filter(
            practice=access.practice,
            client=access.client,
            starts_at__gte=now,
        ).select_related('therapist__user')
        open_invoices = Invoice.objects.filter(
            practice=access.practice,
            client=access.client,
            status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
        ).prefetch_related('payments')
        visible_documents = ClientDocument.objects.filter(
            practice=access.practice,
            client=access.client,
            visible_to_client=True,
        )
        service_packages = ServicePackage.objects.filter(
            practice=access.practice,
            client=access.client,
        )
        portal_requests = ClientPortalRequest.objects.filter(
            practice=access.practice,
            client=access.client,
        )
        pending_intakes = ClientIntakeAssignment.objects.filter(
            practice=access.practice,
            client=access.client,
            status=ClientIntakeAssignment.Status.ASSIGNED,
        ).select_related('template')
        return {
            'portal_access': access,
            'portal_client': access.client,
            'portal_practice': access.practice,
            'upcoming_appointments': upcoming_appointments[:6],
            'next_appointment': upcoming_appointments.first(),
            'visible_documents': visible_documents[:8],
            'open_invoices': open_invoices[:8],
            'open_invoice_total': sum(invoice.balance_due for invoice in open_invoices),
            'service_packages': service_packages[:6],
            'remaining_sessions': sum(package.sessions_remaining for package in service_packages),
            'shared_document_count': visible_documents.count(),
            'portal_request_form': form,
            'portal_requests': portal_requests[:5],
            'open_request_count': portal_requests.exclude(status=ClientPortalRequest.Status.RESOLVED).count(),
            'pending_intakes': pending_intakes,
            'pending_intake_count': pending_intakes.count(),
            'client_payments_ready': bool(settings.STRIPE_SECRET_KEY and access.practice.can_receive_client_payments),
        }

    def post(self, request):
        access = self.get_portal_access()
        form = ClientPortalRequestForm(request.POST, portal_access=access)
        if form.is_valid():
            portal_request = form.save()
            log_audit_event(
                request,
                AuditLog.Action.CREATE,
                'portal.ClientPortalRequest',
                portal_request.pk,
                practice=portal_request.practice,
                metadata={
                    'client_id': portal_request.client_id,
                    'category': portal_request.category,
                    'status': portal_request.status,
                },
            )
            return redirect('portal:dashboard')

        context = self.get_portal_context(access, form)
        context['open_request_modal'] = True
        return TemplateResponse(request, 'portal/dashboard.html', context, status=400)


class ClientConversationListView(ClientPortalAccessMixin, TemplateView):
    template_name = 'portal/conversations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        access = self.get_portal_access()
        open_conversation = self.request.GET.get('open', '')
        if open_conversation:
            PortalMessage.objects.filter(
                conversation__public_id=open_conversation,
                conversation__practice=access.practice,
                conversation__client=access.client,
                author_kind=PortalMessage.AuthorKind.STAFF,
                read_at__isnull=True,
            ).update(read_at=timezone.now())
        context.update({
            'portal_client': access.client,
            'portal_practice': access.practice,
            'conversations': PortalConversation.objects.filter(
                practice=access.practice, client=access.client,
            ).prefetch_related('messages')[:30],
            'conversation_form': kwargs.get('conversation_form') or PortalConversationForm(portal_access=access),
            'open_conversation': open_conversation,
        })
        return context

    def post(self, request, *args, **kwargs):
        access = self.get_portal_access()
        form = PortalConversationForm(request.POST, portal_access=access)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(conversation_form=form), status=400)
        conversation = form.save()
        log_audit_event(
            request, AuditLog.Action.CREATE, 'portal.PortalConversation', conversation.pk,
            practice=conversation.practice, metadata={'client_id': conversation.client_id},
        )
        log_audit_event(
            request, AuditLog.Action.CREATE, 'portal.PortalMessage', conversation.messages.first().pk,
            practice=conversation.practice, metadata={'client_id': conversation.client_id, 'author_kind': PortalMessage.AuthorKind.CLIENT},
        )
        return redirect('portal:conversations')


class ClientConversationDetailView(ClientPortalAccessMixin, TemplateView):
    template_name = 'portal/conversation_detail.html'

    def get_conversation(self):
        access = self.get_portal_access()
        return get_object_or_404(
            PortalConversation.objects.prefetch_related('messages__author'),
            public_id=self.kwargs['public_id'], practice=access.practice, client=access.client,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.get_conversation()
        conversation.messages.filter(
            author_kind=PortalMessage.AuthorKind.STAFF, read_at__isnull=True,
        ).update(read_at=timezone.now())
        context.update({
            'conversation': conversation,
            'portal_practice': conversation.practice,
            'reply_form': kwargs.get('reply_form') or PortalMessageForm(
                conversation=conversation, author=self.request.user, author_kind=PortalMessage.AuthorKind.CLIENT,
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        conversation = self.get_conversation()
        if conversation.status == PortalConversation.Status.RESOLVED:
            messages.error(request, 'This conversation has been resolved by your practice.')
            return redirect('portal:conversation_detail', public_id=conversation.public_id)
        form = PortalMessageForm(
            request.POST, conversation=conversation, author=request.user, author_kind=PortalMessage.AuthorKind.CLIENT,
        )
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(reply_form=form), status=400)
        message = form.save()
        conversation.save(update_fields=['updated_at'])
        log_audit_event(
            request, AuditLog.Action.CREATE, 'portal.PortalMessage', message.pk,
            practice=conversation.practice, metadata={'client_id': conversation.client_id, 'author_kind': message.author_kind},
        )
        if request.POST.get('drawer'):
            return redirect(f"{reverse_lazy('portal:dashboard')}?chat={conversation.public_id}")
        if request.POST.get('next') == 'conversations':
            return redirect(f"{reverse_lazy('portal:conversations')}?open={conversation.public_id}")
        return redirect('portal:conversation_detail', public_id=conversation.public_id)


class AppointmentChangeRequestCreateView(ClientPortalAccessMixin, View):
    def post(self, request, pk):
        access = self.get_portal_access()
        appointment = get_object_or_404(
            Appointment,
            pk=pk,
            practice=access.practice,
            client=access.client,
            status=Appointment.Status.SCHEDULED,
        )
        form = AppointmentChangeRequestForm(request.POST, portal_access=access, appointment=appointment)
        if form.is_valid():
            try:
                portal_request = form.save()
            except IntegrityError:
                form.add_error(None, 'Your practice already has an open change request for this appointment.')
            else:
                log_audit_event(
                    request,
                    AuditLog.Action.CREATE,
                    'portal.ClientPortalRequest',
                    portal_request.pk,
                    practice=portal_request.practice,
                    metadata={
                        'client_id': portal_request.client_id,
                        'appointment_id': appointment.pk,
                        'category': portal_request.category,
                        'status': portal_request.status,
                    },
                )
                messages.success(request, 'Your appointment change request was sent to the practice.')
                return redirect('portal:dashboard')

        dashboard_view = ClientPortalDashboardView()
        dashboard_view.setup(request)
        context = dashboard_view.get_context_data()
        for dashboard_appointment in context['upcoming_appointments']:
            if dashboard_appointment.pk == appointment.pk:
                dashboard_appointment.change_request_form = form
                break
        context['open_appointment_change'] = appointment.pk
        return TemplateResponse(request, 'portal/dashboard.html', context, status=400)


class PublicBookingRequestCreateView(PostRateLimitMixin, View):
    template_name = 'booking/public_booking.html'
    rate_limit_scope = 'public-booking'
    rate_limit_count = 5
    rate_limit_seconds = 3600

    def get_practice(self):
        return get_object_or_404(Practice, public_booking_slug=self.kwargs['slug'])

    def get(self, request, slug):
        practice = self.get_practice()
        selected_date = selected_public_booking_date(request)
        slots = public_booking_slots(practice, selected_date)
        form = PublicBookingRequestForm(practice=practice, available_slots=slots, selected_date=selected_date)
        return TemplateResponse(request, self.template_name, {
            'practice': practice,
            'form': form,
            'selected_date': selected_date,
            'date_options': public_booking_date_options(),
            'available_slots': slots,
        })

    def post(self, request, slug):
        practice = self.get_practice()
        selected_date = selected_public_booking_date(request)
        slots = public_booking_slots(practice, selected_date)
        form = PublicBookingRequestForm(request.POST, practice=practice, available_slots=slots, selected_date=selected_date)
        if form.is_valid():
            booking_request = form.save()
            return TemplateResponse(
                request,
                self.template_name,
                {
                    'practice': practice,
                    'form': PublicBookingRequestForm(practice=practice, available_slots=public_booking_slots(practice, selected_date), selected_date=selected_date),
                    'submitted_request': booking_request,
                    'selected_date': selected_date,
                    'date_options': public_booking_date_options(),
                    'available_slots': slots,
                },
            )
        return TemplateResponse(request, self.template_name, {
            'practice': practice,
            'form': form,
            'selected_date': selected_date,
            'date_options': public_booking_date_options(),
            'available_slots': slots,
        }, status=400)


class PortalAccessListView(PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'intake'
    model = ClientPortalAccess
    template_name = 'settings/portal_access.html'
    context_object_name = 'portal_accesses'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalAccess.objects.none()
        return ClientPortalAccess.objects.filter(practice=practice).select_related('client', 'user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        breadcrumb_client = None
        client_id = self.request.GET.get('client')
        if client_id and client_id.isdigit() and practice:
            breadcrumb_client = practice.clients.filter(pk=client_id).first()
        context['reset_credentials'] = self.request.session.pop('portal_reset_credentials', None)
        context['breadcrumbs'] = (
            [
                {'label': 'Clients', 'url': reverse('clients:list')},
                {'label': str(breadcrumb_client), 'url': reverse('clients:detail', args=[breadcrumb_client.pk])},
                {'label': 'Portal access'},
            ] if breadcrumb_client else [
                {'label': 'Settings'},
                {'label': 'Client Portal Access'},
            ]
        )
        return context


class PortalAccessCreateView(PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'intake'
    permission_action = 'create'
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
    permission_action = 'edit'
    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalAccess.objects.none()
        return ClientPortalAccess.objects.filter(practice=practice)


class PortalAccessDeleteView(PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'intake'
    permission_action = 'delete'
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


class PortalAccessPasswordResetView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'edit'

    def post(self, request, pk):
        practice = self.get_practice()
        access = get_object_or_404(ClientPortalAccess.objects.select_related('client', 'user'), pk=pk, practice=practice)
        password = suggest_portal_password()
        access.user.set_password(password)
        access.user.save(update_fields=['password'])
        profile, _created = UserProfile.objects.update_or_create(
            user=access.user,
            defaults={
                'practice': access.practice,
                'role': UserProfile.Role.CLIENT,
                'must_change_password': True,
            },
        )
        request.session['portal_reset_credentials'] = {
            'access_id': access.pk,
            'client_name': str(access.client),
            'username': access.user.username,
            'password': password,
            'portal_url': request.build_absolute_uri(reverse_lazy('portal:dashboard')),
        }
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'portal.ClientPortalAccess',
            access.pk,
            practice=access.practice,
            metadata={'client_id': access.client_id, 'portal_user_id': access.user_id, 'password_reset': True},
        )
        return redirect('portal_settings:portal_access')


class PracticePortalRequestListView(PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'requests'
    template_name = 'requests/list.html'
    context_object_name = 'request_rows'
    paginate_by = 25

    def get_queryset(self):
        practice = self.get_practice()
        source = self.request.GET.get('source', '')
        self.source = source if source in {'public', 'portal'} else ''
        self.search = self.request.GET.get('q', '').strip()[:200]
        portal = ClientPortalRequest.objects.filter(practice=practice)
        public = PublicBookingRequest.objects.filter(practice=practice)
        if self.search:
            portal = portal.filter(Q(subject__icontains=self.search) | Q(client__first_name__icontains=self.search) | Q(client__last_name__icontains=self.search) | Q(client__email__icontains=self.search))
            public = public.filter(Q(first_name__icontains=self.search) | Q(last_name__icontains=self.search) | Q(email__icontains=self.search))
        portal = portal.order_by().annotate(source=Value('portal', output_field=CharField())).values('pk', 'created_at', 'source')
        public = public.order_by().annotate(source=Value('public', output_field=CharField())).values('pk', 'created_at', 'source')
        rows = public if self.source == 'public' else portal if self.source == 'portal' else public.union(portal, all=True)
        return rows.order_by('-created_at', 'source', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        page_rows = list(context['request_rows'])
        public = {record.pk: record for record in PublicBookingRequest.objects.filter(
            practice=practice, pk__in=[row['pk'] for row in page_rows if row['source'] == 'public'],
        ).select_related('client', 'appointment')}
        portal = {record.pk: record for record in ClientPortalRequest.objects.filter(
            practice=practice, pk__in=[row['pk'] for row in page_rows if row['source'] == 'portal'],
        ).select_related('client', 'appointment')}
        context['request_rows'] = [dict(row, record=(public if row['source'] == 'public' else portal)[row['pk']]) for row in page_rows]
        context['source'] = self.source
        context['q'] = self.search
        context['public_booking_url'] = self.request.build_absolute_uri(reverse_lazy('public_booking', args=[practice.public_booking_slug])) if practice else ''
        return context


class PracticePortalRequestStatusView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'requests'
    permission_action = 'edit'
    def post(self, request, pk):
        practice = self.get_practice()
        portal_request = get_object_or_404(ClientPortalRequest, pk=pk, practice=practice)
        status = request.POST.get('status')
        valid_statuses = {choice for choice, _label in ClientPortalRequest.Status.choices}
        if status in valid_statuses:
            portal_request.status = status
            portal_request.save(update_fields=['status', 'updated_at'])
            log_audit_event(
                request,
                AuditLog.Action.UPDATE,
                'portal.ClientPortalRequest',
                portal_request.pk,
                practice=portal_request.practice,
                metadata={'client_id': portal_request.client_id, 'status': portal_request.status},
            )
        return redirect('portal_requests:list')


class PracticeConversationListView(PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'requests'
    model = PortalConversation
    template_name = 'requests/conversations.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        practice = self.get_practice()
        return PortalConversation.objects.filter(practice=practice).select_related('client').prefetch_related('messages') if practice else PortalConversation.objects.none()


class PracticeConversationDetailView(PracticePermissionMixin, PracticeContextMixin, TemplateView):
    permission_resource = 'requests'
    template_name = 'requests/conversation_detail.html'

    def get_conversation(self):
        return get_object_or_404(
            PortalConversation.objects.prefetch_related('messages__author'),
            public_id=self.kwargs['public_id'], practice=self.get_practice(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.get_conversation()
        conversation.messages.filter(
            author_kind=PortalMessage.AuthorKind.CLIENT, read_at__isnull=True,
        ).update(read_at=timezone.now())
        context.update({
            'conversation': conversation,
            'reply_form': kwargs.get('reply_form') or PortalMessageForm(
                conversation=conversation, author=self.request.user, author_kind=PortalMessage.AuthorKind.STAFF,
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        if not has_practice_permission(request.user, self.permission_resource, 'edit'):
            return permission_redirect(request, 'You do not have permission to reply to or manage client conversations.')
        conversation = self.get_conversation()
        if request.POST.get('action') == 'status':
            status = request.POST.get('status')
            if status in PortalConversation.Status.values:
                conversation.status = status
                conversation.resolved_at = timezone.now() if status == PortalConversation.Status.RESOLVED else None
                conversation.resolved_by = request.user if status == PortalConversation.Status.RESOLVED else None
                conversation.save(update_fields=['status', 'resolved_at', 'resolved_by', 'updated_at'])
                log_audit_event(request, AuditLog.Action.UPDATE, 'portal.PortalConversation', conversation.pk, practice=conversation.practice, metadata={'client_id': conversation.client_id, 'status': status})
            return redirect('portal_requests:conversation_detail', public_id=conversation.public_id)
        if conversation.status == PortalConversation.Status.RESOLVED:
            messages.error(request, 'Reopen the conversation before sending a reply.')
            return redirect('portal_requests:conversation_detail', public_id=conversation.public_id)
        form = PortalMessageForm(request.POST, conversation=conversation, author=request.user, author_kind=PortalMessage.AuthorKind.STAFF)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(reply_form=form), status=400)
        message = form.save()
        conversation.save(update_fields=['updated_at'])
        log_audit_event(request, AuditLog.Action.CREATE, 'portal.PortalMessage', message.pk, practice=conversation.practice, metadata={'client_id': conversation.client_id, 'author_kind': message.author_kind})
        if request.POST.get('drawer'):
            return redirect(f"{reverse_lazy('dashboard')}?chat={conversation.public_id}")
        return redirect('portal_requests:conversation_detail', public_id=conversation.public_id)


class PublicBookingRequestApproveView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'requests'
    permission_action = 'edit'
    def post(self, request, pk):
        practice = self.get_practice()
        booking_request = get_object_or_404(PublicBookingRequest, pk=pk, practice=practice, status=PublicBookingRequest.Status.PENDING)
        therapist = practice.therapists.select_related('user').first()
        if not therapist:
            messages.error(request, 'Add a therapist before approving booking requests.')
            return redirect('portal_requests:list')

        try:
            with transaction.atomic():
                client = Client.objects.filter(practice=practice, email__iexact=booking_request.email).first()
                if not client:
                    client = Client.objects.create(
                        practice=practice,
                        primary_therapist=therapist,
                        first_name=booking_request.first_name,
                        last_name=booking_request.last_name,
                        email=booking_request.email,
                        phone=booking_request.phone,
                    )
                appointment = Appointment(
                    practice=practice,
                    client=client,
                    therapist=therapist,
                    starts_at=booking_request.requested_starts_at,
                    ends_at=booking_request.requested_ends_at,
                    appointment_type=booking_request.appointment_type,
                    notes=f'Created from public booking request.\n\n{booking_request.reason}'.strip(),
                )
                appointment.full_clean()
                appointment.save()
                booking_request.client = client
                booking_request.appointment = appointment
                booking_request.approved_by = request.user
                booking_request.status = PublicBookingRequest.Status.APPROVED
                booking_request.save(update_fields=['client', 'appointment', 'approved_by', 'status', 'updated_at'])
        except ValidationError as exc:
            messages.error(request, f'Booking request could not be approved: {exc}')
            return redirect('portal_requests:list')

        sync_appointment_to_google(appointment)
        log_audit_event(
            request,
            AuditLog.Action.CREATE,
            'appointments.Appointment',
            appointment.pk,
            practice=practice,
            metadata={'client_id': client.pk, 'public_booking_request_id': booking_request.pk},
        )
        messages.success(request, 'Booking request approved and appointment created.')
        return redirect('portal_requests:list')


class PublicBookingRequestDeclineView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'requests'
    permission_action = 'edit'
    def post(self, request, pk):
        practice = self.get_practice()
        booking_request = get_object_or_404(PublicBookingRequest, pk=pk, practice=practice, status=PublicBookingRequest.Status.PENDING)
        booking_request.status = PublicBookingRequest.Status.DECLINED
        booking_request.save(update_fields=['status', 'updated_at'])
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'portal.PublicBookingRequest',
            booking_request.pk,
            practice=practice,
            metadata={'status': booking_request.status},
        )
        messages.success(request, 'Booking request declined.')
        return redirect('portal_requests:list')


class PracticeIntakeListView(PracticePermissionMixin, PracticeContextMixin, TemplateView):
    permission_resource = 'intake'
    template_name = 'intake/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        assignments = ClientIntakeAssignment.objects.filter(practice=practice)
        counts = dict(assignments.values_list('status').annotate(count=Count('pk')))
        context['intake_counts'] = {key: counts.get(key, 0) for key in ClientIntakeAssignment.Status.values}
        context['intake_counts']['total'] = sum(counts.values())
        query = self.request.GET.get('q', '').strip()[:160]
        status = self.request.GET.get('status', '')
        if status not in ClientIntakeAssignment.Status.values:
            status = ''
        if query:
            assignments = assignments.annotate(client_name=Concat('client__first_name', Value(' '), 'client__last_name')).filter(
                Q(client_name__icontains=query)
                | Q(template_snapshot__name__icontains=query))
        if status:
            assignments = assignments.filter(status=status)
        page = Paginator(assignments.select_related('client', 'template').defer('answers'), 20).get_page(self.request.GET.get('page'))
        context.update(q=query, status=status, page_obj=page, assignments=page.object_list)
        context['templates'] = IntakePacketTemplate.objects.filter(practice=practice)
        context['can_create_intake'] = has_practice_permission(self.request.user, 'intake', 'create')
        context['can_edit_intake'] = has_practice_permission(self.request.user, 'intake', 'edit')
        context['template_form'] = IntakePacketTemplateForm(practice=practice, auto_id='intake-template-create-%s')
        context['assignment_form'] = ClientIntakeAssignmentForm(practice=practice, assigned_by=self.request.user, auto_id='intake-assignment-%s')
        return context


class IntakeTemplateCreateView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'create'

    def post(self, request):
        practice = self.get_practice()
        form = IntakePacketTemplateForm(request.POST, practice=practice)
        if not form.is_valid():
            return TemplateResponse(request, 'intake/template_form.html', {'form': form, 'intake_template': None})
        template = form.save()
        log_audit_event(request, AuditLog.Action.CREATE, 'portal.IntakePacketTemplate', template.pk, practice=practice, metadata={'name': template.name})
        messages.success(request, 'Intake template created.')
        return redirect('intake:list')


class IntakeTemplateUpdateView(PracticePermissionMixin, PracticeContextMixin, UpdateView):
    permission_resource = 'intake'
    permission_action = 'edit'
    model = IntakePacketTemplate
    form_class = IntakePacketTemplateForm
    template_name = 'intake/template_form.html'
    context_object_name = 'intake_template'
    success_url = reverse_lazy('intake:list')

    def get_queryset(self):
        return super().get_queryset().filter(practice=self.get_practice())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(self.request, AuditLog.Action.UPDATE, 'portal.IntakePacketTemplate', self.object.pk, practice=self.get_practice(), metadata={'active': self.object.active})
        messages.success(self.request, 'Template updated. Previously assigned packets keep their original questions.')
        return response


class ClientIntakeAssignView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'create'

    def post(self, request):
        practice = self.get_practice()
        form = ClientIntakeAssignmentForm(request.POST, practice=practice, assigned_by=request.user)
        if not form.is_valid():
            return TemplateResponse(request, 'intake/assignment_form.html', {'form': form})
        assignment = form.save()
        log_audit_event(request, AuditLog.Action.CREATE, 'portal.ClientIntakeAssignment', assignment.pk,
                        practice=practice, metadata={'client_id': assignment.client_id, 'template_id': assignment.template_id})
        messages.success(request, 'Intake packet assigned. The patient can complete it in their portal.')
        return redirect('intake:list')


class ClientIntakeResponsesView(PracticePermissionMixin, PracticeContextMixin, TemplateView):
    permission_resource = 'intake'
    template_name = 'intake/responses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = get_object_or_404(ClientIntakeAssignment.objects.select_related('client', 'template', 'reviewed_by'),
                                       pk=self.kwargs['pk'], practice=self.get_practice())
        items = assignment.response_items
        can_edit = has_practice_permission(self.request.user, 'intake', 'edit')
        context.update(assignment=assignment, response_items=items, can_edit_intake=can_edit,
                       can_review=can_edit and assignment.status == ClientIntakeAssignment.Status.SUBMITTED)
        return context


class ClientIntakeReviewView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'edit'

    def post(self, request, pk):
        practice = self.get_practice()
        with transaction.atomic():
            assignment = get_object_or_404(ClientIntakeAssignment.objects.select_for_update(), pk=pk, practice=practice)
            if assignment.status == ClientIntakeAssignment.Status.ASSIGNED:
                messages.error(request, 'This packet has not been submitted yet.')
                return redirect('intake:list')
            if assignment.status == ClientIntakeAssignment.Status.SUBMITTED:
                assignment.status = ClientIntakeAssignment.Status.REVIEWED
                assignment.reviewed_at = timezone.now()
                assignment.reviewed_by = request.user
                assignment.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'updated_at'])
                log_audit_event(request, AuditLog.Action.UPDATE, 'portal.ClientIntakeAssignment', assignment.pk,
                                practice=practice, metadata={'client_id': assignment.client_id, 'status': assignment.status})
                messages.success(request, 'Intake responses marked as reviewed.')
        return redirect('intake:list')


class ClientIntakeCompleteView(ClientPortalAccessMixin, FormView):
    template_name = 'portal/intake_form.html'
    form_class = ClientIntakeResponseForm
    success_url = reverse_lazy('portal:dashboard')

    def get_assignment(self):
        access = self.get_portal_access()
        return get_object_or_404(
            ClientIntakeAssignment.objects.select_related('template', 'client'),
            pk=self.kwargs['pk'],
            practice=access.practice,
            client=access.client,
            status=ClientIntakeAssignment.Status.ASSIGNED,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['assignment'] = self.get_assignment()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assignment'] = self.get_assignment()
        return context

    def form_valid(self, form):
        assignment = form.save()
        log_audit_event(
            self.request,
            AuditLog.Action.UPDATE,
            'portal.ClientIntakeAssignment',
            assignment.pk,
            practice=assignment.practice,
            metadata={'client_id': assignment.client_id, 'status': assignment.status},
        )
        return super().form_valid(form)
