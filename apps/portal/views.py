from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView
import stripe
from django.conf import settings

from apps.accounts.access import ClientPortalRedirectMixin, ForcePasswordChangeRequiredMixin, PracticePermissionMixin, get_practice_for_user
from apps.accounts.models import UserProfile
from apps.appointments.google_calendar import sync_appointment_to_google
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.billing.models import Invoice, ServicePackage
from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.practices.models import Practice
from .forms import (
    ClientIntakeAssignmentForm,
    ClientIntakeResponseForm,
    AppointmentChangeRequestForm,
    ClientPortalAccessForm,
    ClientPortalRequestForm,
    IntakePacketTemplateForm,
    PublicBookingRequestForm,
    suggest_portal_password,
    suggest_portal_username,
)
from .models import ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate, PublicBookingRequest


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
        upcoming_appointments = Appointment.objects.filter(
            practice=access.practice,
            client=access.client,
            starts_at__gte=now,
        ).select_related('therapist__user')
        open_invoices = Invoice.objects.filter(
            practice=access.practice,
            client=access.client,
        ).exclude(status__in=[Invoice.Status.PAID, Invoice.Status.VOID])
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
        context.update({
            'upcoming_appointments': upcoming_appointments[:6],
            'next_appointment': upcoming_appointments.first(),
            'visible_documents': visible_documents[:8],
            'open_invoices': open_invoices[:8],
            'open_invoice_total': open_invoices.aggregate(total=Sum('amount'))['total'] or 0,
            'service_packages': service_packages[:6],
            'remaining_sessions': sum(package.sessions_remaining for package in service_packages),
            'shared_document_count': visible_documents.count(),
            'portal_request_form': ClientPortalRequestForm(portal_access=access),
            'portal_requests': portal_requests[:5],
            'open_request_count': portal_requests.exclude(status=ClientPortalRequest.Status.RESOLVED).count(),
            'pending_intakes': pending_intakes,
            'pending_intake_count': pending_intakes.count(),
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
        if invoice.status in {Invoice.Status.PAID, Invoice.Status.VOID} or invoice.amount <= 0:
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
                        'unit_amount': int(invoice.amount * 100),
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
        ).exclude(status__in=[Invoice.Status.PAID, Invoice.Status.VOID])
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
            'open_invoice_total': open_invoices.aggregate(total=Sum('amount'))['total'] or 0,
            'service_packages': service_packages[:6],
            'remaining_sessions': sum(package.sessions_remaining for package in service_packages),
            'shared_document_count': visible_documents.count(),
            'portal_request_form': form,
            'portal_requests': portal_requests[:5],
            'open_request_count': portal_requests.exclude(status=ClientPortalRequest.Status.RESOLVED).count(),
            'pending_intakes': pending_intakes,
            'pending_intake_count': pending_intakes.count(),
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
            portal_request = form.save()
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
        return redirect('portal:dashboard')


class PublicBookingRequestCreateView(View):
    template_name = 'booking/public_booking.html'

    def get_practice(self):
        return get_object_or_404(Practice, public_booking_slug=self.kwargs['slug'])

    def get(self, request, slug):
        practice = self.get_practice()
        form = PublicBookingRequestForm(practice=practice)
        return TemplateResponse(request, self.template_name, {'practice': practice, 'form': form})

    def post(self, request, slug):
        practice = self.get_practice()
        form = PublicBookingRequestForm(request.POST, practice=practice)
        if form.is_valid():
            booking_request = form.save()
            return TemplateResponse(
                request,
                self.template_name,
                {'practice': practice, 'form': PublicBookingRequestForm(practice=practice), 'submitted_request': booking_request},
            )
        return TemplateResponse(request, self.template_name, {'practice': practice, 'form': form}, status=400)


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
        context['reset_credentials'] = self.request.session.pop('portal_reset_credentials', None)
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


class PortalAccessPasswordResetView(PracticeContextMixin, View):
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
    model = ClientPortalRequest
    template_name = 'requests/list.html'
    context_object_name = 'portal_requests'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalRequest.objects.none()
        return ClientPortalRequest.objects.filter(practice=practice).select_related('client', 'submitted_by', 'appointment')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['booking_requests'] = PublicBookingRequest.objects.filter(practice=practice).select_related('client', 'appointment', 'approved_by') if practice else PublicBookingRequest.objects.none()
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
        context['templates'] = IntakePacketTemplate.objects.filter(practice=practice)
        context['assignments'] = ClientIntakeAssignment.objects.filter(practice=practice).select_related('client', 'template')
        context['template_form'] = IntakePacketTemplateForm(practice=practice)
        context['assignment_form'] = ClientIntakeAssignmentForm(practice=practice, assigned_by=self.request.user)
        return context


class IntakeTemplateCreateView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'create'
    def post(self, request):
        practice = self.get_practice()
        form = IntakePacketTemplateForm(request.POST, practice=practice)
        if form.is_valid():
            template = form.save()
            log_audit_event(request, AuditLog.Action.CREATE, 'portal.IntakePacketTemplate', template.pk, practice=practice, metadata={'name': template.name})
        return redirect('intake:list')


class ClientIntakeAssignView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'create'
    def post(self, request):
        practice = self.get_practice()
        form = ClientIntakeAssignmentForm(request.POST, practice=practice, assigned_by=request.user)
        if form.is_valid():
            assignment = form.save()
            log_audit_event(
                request,
                AuditLog.Action.CREATE,
                'portal.ClientIntakeAssignment',
                assignment.pk,
                practice=practice,
                metadata={'client_id': assignment.client_id, 'template_id': assignment.template_id},
            )
        return redirect('intake:list')


class ClientIntakeReviewView(PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'intake'
    permission_action = 'edit'
    def post(self, request, pk):
        practice = self.get_practice()
        assignment = get_object_or_404(ClientIntakeAssignment, pk=pk, practice=practice)
        assignment.status = ClientIntakeAssignment.Status.REVIEWED
        assignment.reviewed_at = timezone.now()
        assignment.reviewed_by = request.user
        assignment.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'updated_at'])
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'portal.ClientIntakeAssignment',
            assignment.pk,
            practice=practice,
            metadata={'client_id': assignment.client_id, 'status': assignment.status},
        )
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
