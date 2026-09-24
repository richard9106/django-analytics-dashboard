from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
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


class SessionNoteListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = SessionNote
    template_name = 'clinical/list.html'
    context_object_name = 'notes'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return (
            SessionNote.objects.filter(practice=practice)
            .select_related('client', 'therapist__user', 'appointment', 'treatment_plan')
            .order_by('-created_at')
        )


class SessionNoteCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
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


class SessionNoteUpdateView(LoginRequiredMixin, PracticeContextMixin, UpdateView):
    model = SessionNote
    form_class = SessionNoteForm
    template_name = 'clinical/form.html'
    success_url = reverse_lazy('clinical:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return SessionNote.objects.filter(practice=practice)

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
        response = super().form_valid(form)
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


class SessionNoteDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = SessionNote
    success_url = reverse_lazy('clinical:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return SessionNote.objects.filter(practice=practice)

    def form_valid(self, form):
        note_id = self.object.pk
        practice = self.object.practice
        metadata = {
            'client_id': self.object.client_id,
            'appointment_id': self.object.appointment_id,
            'treatment_plan_id': self.object.treatment_plan_id,
        }
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.DELETE,
            'clinical.SessionNote',
            note_id,
            practice=practice,
            metadata=metadata,
        )
        return response


class TreatmentPlanListView(LoginRequiredMixin, TreatmentPlanContextMixin, ListView):
    model = TreatmentPlan
    template_name = 'clinical/treatment_plans.html'
    context_object_name = 'plans'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return TreatmentPlan.objects.none()
        return (
            TreatmentPlan.objects.filter(practice=practice)
            .select_related('client', 'therapist__user')
            .prefetch_related('diagnoses')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['diagnoses'] = (
            practice.diagnoses.select_related('client').all() if practice else Diagnosis.objects.none()
        )
        context['default_next_review_date'] = timezone.localdate() + timedelta(days=90)
        return context


class TreatmentPlanCreateView(LoginRequiredMixin, TreatmentPlanContextMixin, CreateView):
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


class TreatmentPlanUpdateView(LoginRequiredMixin, TreatmentPlanContextMixin, UpdateView):
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


class TreatmentPlanDeleteView(LoginRequiredMixin, TreatmentPlanContextMixin, DeleteView):
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
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.DELETE,
            'clinical.TreatmentPlan',
            plan_id,
            practice=practice,
            metadata=metadata,
        )
        return response


class TreatmentPlanCompleteReviewView(LoginRequiredMixin, TreatmentPlanContextMixin, View):
    def post(self, request, *args, **kwargs):
        practice = self.get_practice()
        if not practice:
            return redirect('clinical:treatment_plans')

        plan = get_object_or_404(TreatmentPlan, pk=kwargs['pk'], practice=practice)
        next_review_date = request.POST.get('next_review_date')
        plan.status = TreatmentPlan.Status.ACTIVE
        if next_review_date:
            plan.review_date = date.fromisoformat(next_review_date)
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


class DiagnosisCreateView(LoginRequiredMixin, TreatmentPlanContextMixin, CreateView):
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


class DiagnosisUpdateView(LoginRequiredMixin, TreatmentPlanContextMixin, UpdateView):
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


class DiagnosisDeleteView(LoginRequiredMixin, TreatmentPlanContextMixin, DeleteView):
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
