from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, ForcePasswordChangeRequiredMixin, get_practice_for_user
from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.billing.models import Invoice, ServicePackage
from apps.documents.models import ClientDocument
from .forms import (
    ClientIntakeAssignmentForm,
    ClientIntakeResponseForm,
    ClientPortalAccessForm,
    ClientPortalRequestForm,
    IntakePacketTemplateForm,
    suggest_portal_password,
    suggest_portal_username,
)
from .models import ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate


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


class PortalAccessListView(PracticeContextMixin, ListView):
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


class PracticePortalRequestListView(PracticeContextMixin, ListView):
    model = ClientPortalRequest
    template_name = 'requests/list.html'
    context_object_name = 'portal_requests'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientPortalRequest.objects.none()
        return ClientPortalRequest.objects.filter(practice=practice).select_related('client', 'submitted_by')


class PracticePortalRequestStatusView(PracticeContextMixin, View):
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


class PracticeIntakeListView(PracticeContextMixin, TemplateView):
    template_name = 'intake/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['templates'] = IntakePacketTemplate.objects.filter(practice=practice)
        context['assignments'] = ClientIntakeAssignment.objects.filter(practice=practice).select_related('client', 'template')
        context['template_form'] = IntakePacketTemplateForm(practice=practice)
        context['assignment_form'] = ClientIntakeAssignmentForm(practice=practice, assigned_by=self.request.user)
        return context


class IntakeTemplateCreateView(PracticeContextMixin, View):
    def post(self, request):
        practice = self.get_practice()
        form = IntakePacketTemplateForm(request.POST, practice=practice)
        if form.is_valid():
            template = form.save()
            log_audit_event(request, AuditLog.Action.CREATE, 'portal.IntakePacketTemplate', template.pk, practice=practice, metadata={'name': template.name})
        return redirect('intake:list')


class ClientIntakeAssignView(PracticeContextMixin, View):
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


class ClientIntakeReviewView(PracticeContextMixin, View):
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
