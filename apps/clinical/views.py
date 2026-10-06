from collections import OrderedDict
from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, Http404
from django.urls import reverse
from apps.clients.models import Client
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, PracticePermissionMixin, get_practice_for_user, has_practice_permission
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.appointments.workflow import SessionWorkflowMixin
from .forms import DiagnosisForm, SessionNoteForm, TreatmentPlanForm
from .models import Diagnosis, SessionNote, TreatmentPlan


class PracticeContextMixin(ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['practice'] = practice
        if practice:
            context['note_clients'] = practice.clients.all()
            context['note_therapists'] = practice.therapists.select_related('user')
            context['note_appointments'] = practice.appointments.select_related('client', 'therapist__user')
            context['note_treatment_plans'] = practice.treatment_plans.select_related('client')
        else:
            context['note_clients'] = []
            context['note_therapists'] = []
            context['note_appointments'] = []
            context['note_treatment_plans'] = []
        return context


class TreatmentPlanContextMixin(PracticeContextMixin):
    success_url = reverse_lazy('clinical:treatment_plans')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        if practice:
            context['plan_clients'] = practice.clients.all()
            context['plan_therapists'] = practice.therapists.select_related('user')
            context['diagnosis_options'] = practice.diagnoses.select_related('client').filter(active=True)
        else:
            context['plan_clients'] = []
            context['plan_therapists'] = []
            context['diagnosis_options'] = []
        context['today'] = timezone.localdate()
        return context


class SessionNoteListView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'clinical'
    model = SessionNote
    template_name = 'clinical/list.html'
    context_object_name = 'notes'

    def get_note_filters(self):
        return {
            'q': self.request.GET.get('q', '').strip(),
            'client': self.request.GET.get('client', ''),
            'therapist': self.request.GET.get('therapist', ''),
            'appointment': self.request.GET.get('appointment', ''),
            'note_type': self.request.GET.get('note_type', ''),
            'status': self.request.GET.get('status', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        notes = (
            SessionNote.objects.filter(practice=practice)
            .select_related('client', 'therapist__user', 'appointment', 'treatment_plan')
            .order_by('client__last_name', 'client__first_name', '-updated_at', '-pk')
        )
        filters = self.get_note_filters()

        if filters['q']:
            notes = notes.filter(
                Q(content__icontains=filters['q'])
                | Q(treatment_progress__icontains=filters['q'])
                | Q(client__first_name__icontains=filters['q'])
                | Q(client__last_name__icontains=filters['q'])
                | Q(treatment_plan__title__icontains=filters['q'])
            )
        if filters['client'].isdigit():
            notes = notes.filter(client_id=filters['client'])
        if filters['therapist'].isdigit():
            notes = notes.filter(therapist_id=filters['therapist'])
        if filters['appointment'].isdigit():
            notes = notes.filter(appointment_id=filters['appointment'])
        valid_note_types = {choice for choice, _label in SessionNote.NoteType.choices}
        if filters['note_type'] in valid_note_types:
            notes = notes.filter(note_type=filters['note_type'])
        if filters['status'] == 'locked':
            notes = notes.filter(is_locked=True)
        elif filters['status'] == 'draft':
            notes = notes.filter(is_locked=False)
        try:
            if filters['date_from']:
                notes = notes.filter(updated_at__date__gte=date.fromisoformat(filters['date_from']))
            if filters['date_to']:
                notes = notes.filter(updated_at__date__lte=date.fromisoformat(filters['date_to']))
        except ValueError:
            pass
        return notes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notes = list(context['notes'])
        groups = OrderedDict()
        for note in notes:
            group = groups.setdefault(note.client_id, {'client': note.client, 'notes': []})
            group['notes'].append(note)
        context['notes'] = notes
        context['note_groups'] = list(groups.values())
        context['note_filters'] = self.get_note_filters()
        context['note_type_choices'] = SessionNote.NoteType.choices
        return context


class SessionNoteCreateView(LoginRequiredMixin, PracticePermissionMixin, SessionWorkflowMixin, PracticeContextMixin, CreateView):
    permission_resource = 'clinical'
    permission_action = 'create'
    model = SessionNote
    form_class = SessionNoteForm
    template_name = 'clinical/form.html'
    success_url = reverse_lazy('clinical:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Clinical Note'
        context['form_heading'] = 'Document a client session'
        context['submit_label'] = 'Create note'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            'clinical.SessionNote',
            self.object.pk,
            practice=self.object.practice,
            metadata={
                'client_id': self.object.client_id,
                'appointment_id': self.object.appointment_id,
                'treatment_plan_id': self.object.treatment_plan_id,
            },
        )
        return response


class SessionNoteUpdateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, UpdateView):
    permission_resource = 'clinical'
    permission_action = 'edit'
    model = SessionNote
    form_class = SessionNoteForm
    template_name = 'clinical/form.html'
    success_url = reverse_lazy('clinical:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        # Locked notes are finalized records. Excluding them here prevents direct
        # URL access and protects both GET and POST update attempts.
        return SessionNote.objects.filter(practice=practice, is_locked=False)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Clinical Note'
        context['form_heading'] = 'Edit note details'
        context['submit_label'] = 'Save changes'
        context['show_delete_action'] = True
        return context

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ValidationError:
            self.request._audit_denied_reason = 'finalized_note_immutable'
            form.add_error(None, 'This note has been finalized and can no longer be edited.')
            return self.form_invalid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.UPDATE,
            'clinical.SessionNote',
            self.object.pk,
            practice=self.object.practice,
            metadata={
                'client_id': self.object.client_id,
                'appointment_id': self.object.appointment_id,
                'treatment_plan_id': self.object.treatment_plan_id,
                'is_locked': self.object.is_locked,
            },
        )
        return response


class SessionNoteDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'clinical'
    permission_action = 'delete'
    model = SessionNote
    success_url = reverse_lazy('clinical:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return SessionNote.objects.filter(practice=practice, is_locked=False)

    def form_valid(self, form):
        note_id = self.object.pk
        practice = self.object.practice
        metadata = {
            'client_id': self.object.client_id,
            'appointment_id': self.object.appointment_id,
            'treatment_plan_id': self.object.treatment_plan_id,
        }
        try:
            response = super().form_valid(form)
        except ValidationError:
            self.request._audit_denied_reason = 'clinical_note_finalized'
            messages.error(self.request, 'This note was finalized and cannot be deleted.')
            return redirect('clinical:list')
        log_audit_event(
            self.request,
            AuditLog.Action.DELETE,
            'clinical.SessionNote',
            note_id,
            practice=practice,
            metadata=metadata,
        )
        return response


class TreatmentPlanListView(LoginRequiredMixin, PracticePermissionMixin, TreatmentPlanContextMixin, ListView):
    permission_resource = 'clinical'
    model = TreatmentPlan
    template_name = 'clinical/treatment_plans.html'
    context_object_name = 'plans'

    def get_plan_filters(self):
        return {
            'q': self.request.GET.get('q', '').strip(),
            'client': self.request.GET.get('client', ''),
            'therapist': self.request.GET.get('therapist', ''),
            'diagnosis': self.request.GET.get('diagnosis', ''),
            'status': self.request.GET.get('status', ''),
            'review_from': self.request.GET.get('review_from', ''),
            'review_to': self.request.GET.get('review_to', ''),
        }

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return TreatmentPlan.objects.none()
        plans = (
            TreatmentPlan.objects.filter(practice=practice)
            .select_related('client', 'therapist__user')
            .prefetch_related('diagnoses')
            .order_by('client__last_name', 'client__first_name', 'review_date', '-updated_at', '-pk')
        )
        filters = self.get_plan_filters()

        if filters['q']:
            plans = plans.filter(
                Q(title__icontains=filters['q'])
                | Q(goals__icontains=filters['q'])
                | Q(objectives__icontains=filters['q'])
                | Q(interventions__icontains=filters['q'])
                | Q(client__first_name__icontains=filters['q'])
                | Q(client__last_name__icontains=filters['q'])
                | Q(diagnoses__code__icontains=filters['q'])
                | Q(diagnoses__label__icontains=filters['q'])
            )
        if filters['client'].isdigit():
            plans = plans.filter(client_id=filters['client'])
        if filters['therapist'].isdigit():
            plans = plans.filter(therapist_id=filters['therapist'])
        if filters['diagnosis'].isdigit():
            plans = plans.filter(diagnoses__id=filters['diagnosis'])
        valid_statuses = {choice for choice, _label in TreatmentPlan.Status.choices}
        if filters['status'] in valid_statuses:
            plans = plans.filter(status=filters['status'])
        try:
            if filters['review_from']:
                plans = plans.filter(review_date__gte=date.fromisoformat(filters['review_from']))
            if filters['review_to']:
                plans = plans.filter(review_date__lte=date.fromisoformat(filters['review_to']))
        except ValueError:
            pass
        return plans.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        plans = list(context['plans'])
        groups = OrderedDict()
        for plan in plans:
            group = groups.setdefault(plan.client_id, {'client': plan.client, 'plans': []})
            group['plans'].append(plan)
        context['plans'] = plans
        context['plan_groups'] = list(groups.values())
        context['plan_filters'] = self.get_plan_filters()
        client_filter = context['plan_filters']['client']
        if practice and client_filter.isascii() and client_filter.isdigit() and len(client_filter) <= 18:
            context['diagnosis_options'] = context['diagnosis_options'].filter(client_id=client_filter)
        context['plan_status_choices'] = TreatmentPlan.Status.choices
        context['default_next_review_date'] = timezone.localdate() + timedelta(days=90)
        return context


class TreatmentPlanCreateView(LoginRequiredMixin, PracticePermissionMixin, TreatmentPlanContextMixin, CreateView):
    permission_resource = 'clinical'
    permission_action = 'create'
    model = TreatmentPlan
    form_class = TreatmentPlanForm
    template_name = 'clinical/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Treatment Plan'
        context['form_heading'] = 'Create a care plan'
        context['submit_label'] = 'Create plan'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            'clinical.TreatmentPlan',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'status': self.object.status},
        )
        return response


class TreatmentPlanUpdateView(LoginRequiredMixin, PracticePermissionMixin, TreatmentPlanContextMixin, UpdateView):
    permission_resource = 'clinical'
    permission_action = 'edit'
    model = TreatmentPlan
    form_class = TreatmentPlanForm
    template_name = 'clinical/form.html'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return TreatmentPlan.objects.none()
        return TreatmentPlan.objects.filter(practice=practice)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Treatment Plan'
        context['form_heading'] = 'Edit care plan details'
        context['submit_label'] = 'Save changes'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.UPDATE,
            'clinical.TreatmentPlan',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'status': self.object.status},
        )
        return response


class TreatmentPlanDeleteView(LoginRequiredMixin, PracticePermissionMixin, TreatmentPlanContextMixin, DeleteView):
    permission_resource = 'clinical'
    permission_action = 'delete'
    model = TreatmentPlan

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return TreatmentPlan.objects.none()
        return TreatmentPlan.objects.filter(practice=practice)

    def form_valid(self, form):
        plan_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'status': self.object.status}
        try:
            response = super().form_valid(form)
        except ProtectedError:
            self.request._audit_denied_reason = 'clinical_record_retained'
            messages.error(self.request, 'This plan is referenced by clinical notes and must be retained. Update its status instead.')
            return redirect('clinical:treatment_plans')
        log_audit_event(
            self.request,
            AuditLog.Action.DELETE,
            'clinical.TreatmentPlan',
            plan_id,
            practice=practice,
            metadata=metadata,
        )
        return response


class TreatmentPlanCompleteReviewView(LoginRequiredMixin, PracticePermissionMixin, TreatmentPlanContextMixin, View):
    permission_resource = 'clinical'
    permission_action = 'edit'
    def post(self, request, *args, **kwargs):
        practice = self.get_practice()
        if not practice:
            return redirect('clinical:treatment_plans')

        plan = get_object_or_404(TreatmentPlan, pk=kwargs['pk'], practice=practice)
        next_review_date = request.POST.get('next_review_date')
        plan.status = TreatmentPlan.Status.ACTIVE
        if next_review_date:
            parsed_review_date = parse_date(next_review_date)
            if not parsed_review_date:
                return redirect('clinical:treatment_plans')
            plan.review_date = parsed_review_date
        else:
            plan.review_date = timezone.localdate() + timedelta(days=90)
        plan.full_clean()
        plan.save(update_fields=['status', 'review_date', 'updated_at'])
        log_audit_event(
            request,
            AuditLog.Action.UPDATE,
            'clinical.TreatmentPlan',
            plan.pk,
            practice=plan.practice,
            metadata={'client_id': plan.client_id, 'status': plan.status, 'review_date': plan.review_date.isoformat()},
        )
        return redirect('clinical:treatment_plans')


class DiagnosisOptionsView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'clinical'

    def get(self, request, client_pk):
        if not 0 < client_pk <= 9223372036854775807:
            raise Http404
        client = get_object_or_404(Client, pk=client_pk, practice=self.get_practice())
        diagnoses = Diagnosis.objects.filter(client=client, practice=client.practice)
        return JsonResponse({'diagnoses': list(diagnoses.values('id', 'code', 'label', 'active'))})


class PatientDiagnosisMixin:
    def form_invalid(self, form):
        patient = self.get_patient()
        if (self.request.POST.get('return_to_patient') == '1' and patient
                and has_practice_permission(self.request.user, 'clients', 'view')
                and has_practice_permission(self.request.user, 'clinical', 'view')):
            from apps.clients.views import ClientDetailView
            view = ClientDetailView()
            view.setup(self.request, pk=patient.pk)
            view.object = view.get_object()
            context = view.get_context_data()
            if getattr(self, 'object', None):
                form.auto_id = f'diagnosis-edit-{self.object.pk}-%s'
                context['diagnosis_edit_forms'] = [
                    (diagnosis, form if diagnosis.pk == self.object.pk else existing)
                    for diagnosis, existing in context.get('diagnosis_edit_forms', [])
                ]
                context['diagnosis_modal_id'] = f'diagnosis-edit-{self.object.pk}'
            else:
                form.auto_id = 'diagnosis-create-%s'
                context['diagnosis_create_form'] = form
                context['diagnosis_modal_id'] = 'diagnosis-create-modal'
            return render(self.request, 'clients/detail.html', context)
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Diagnosis saved to the patient record.')
        return response

    def get_patient(self):
        if getattr(self, 'object', None):
            return self.object.client
        value = self.request.GET.get('client')
        if value:
            if not value.isascii() or not value.isdigit() or len(value) > 18:
                raise Http404
            return get_object_or_404(Client, pk=value, practice=self.get_practice())

    def get_initial(self):
        initial = super().get_initial()
        patient = self.get_patient()
        if patient:
            initial['client'] = patient.pk
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['patient'] = self.get_patient()
        return kwargs

    def get_success_url(self):
        if has_practice_permission(self.request.user, 'clients', 'view'):
            return reverse('clients:detail', args=[self.object.client_id])
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['diagnosis_patient'] = self.get_patient()
        context['is_diagnosis_form'] = True
        return context


class DiagnosisCreateView(LoginRequiredMixin, PracticePermissionMixin, PatientDiagnosisMixin, TreatmentPlanContextMixin, CreateView):
    permission_resource = 'clinical'
    permission_action = 'create'
    model = Diagnosis
    form_class = DiagnosisForm
    template_name = 'clinical/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Diagnosis'
        context['form_heading'] = 'Add client diagnosis'
        context['submit_label'] = 'Add diagnosis'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            'clinical.Diagnosis',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'code': self.object.code},
        )
        return response


class DiagnosisUpdateView(LoginRequiredMixin, PracticePermissionMixin, PatientDiagnosisMixin, TreatmentPlanContextMixin, UpdateView):
    permission_resource = 'clinical'
    permission_action = 'edit'
    model = Diagnosis
    form_class = DiagnosisForm
    template_name = 'clinical/form.html'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Diagnosis.objects.none()
        return Diagnosis.objects.filter(practice=practice)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Diagnosis'
        context['form_heading'] = 'Edit diagnosis details'
        context['submit_label'] = 'Save changes'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.UPDATE,
            'clinical.Diagnosis',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'code': self.object.code, 'active': self.object.active},
        )
        return response


class DiagnosisDeleteView(LoginRequiredMixin, PracticePermissionMixin, TreatmentPlanContextMixin, DeleteView):
    permission_resource = 'clinical'
    permission_action = 'delete'
    model = Diagnosis

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Diagnosis.objects.none()
        return Diagnosis.objects.filter(practice=practice)

    def form_valid(self, form):
        diagnosis_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'code': self.object.code}
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.DELETE,
            'clinical.Diagnosis',
            diagnosis_id,
            practice=practice,
            metadata=metadata,
        )
        return response
