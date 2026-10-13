from django import forms
from django.utils import timezone
from django.db.models import Q

from .models import Diagnosis, SessionNote, TreatmentPlan


class SessionNoteForm(forms.ModelForm):
    class Meta:
        model = SessionNote
        fields = [
            'client',
            'therapist',
            'appointment',
            'treatment_plan',
            'note_type',
            'content',
            'treatment_progress',
            'is_locked',
        ]
        labels = {'is_locked': 'Lock without signing'}
        widgets = {
            'content': forms.Textarea(attrs={'rows': 8}),
            'treatment_progress': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, user=None, appointment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice

        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['therapist'].queryset = practice.therapists.select_related('user')
            self.fields['appointment'].queryset = practice.appointments.select_related('client', 'therapist__user')
            self.fields['treatment_plan'].queryset = practice.treatment_plans.select_related('client')
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['therapist'].queryset = self.fields['therapist'].queryset.none()
            self.fields['appointment'].queryset = self.fields['appointment'].queryset.none()
            self.fields['treatment_plan'].queryset = self.fields['treatment_plan'].queryset.none()

        if user:
            from apps.appointments.access import scope_sessions, manages_sessions
            self.fields['appointment'].queryset = scope_sessions(self.fields['appointment'].queryset, user)
            if not manages_sessions(user):
                self.fields['therapist'].queryset = self.fields['therapist'].queryset.filter(user=user)

        selected_client = appointment.client_id if appointment else (
            self.data.get(self.add_prefix('client')) if self.is_bound else self.initial.get('client')
        )
        selected_client = str(getattr(selected_client, 'pk', selected_client) or '')
        if selected_client.isascii() and selected_client.isdigit() and len(selected_client) <= 18:
            self.fields['appointment'].queryset = self.fields['appointment'].queryset.filter(client_id=selected_client).order_by('-starts_at', '-pk')
        else:
            self.fields['appointment'].queryset = self.fields['appointment'].queryset.none()
        self.fields['appointment'].empty_label = 'No appointment'

        if appointment:
            self.fields['note_type'].choices = [(value, label) for value, label in SessionNote.NoteType.choices if value != SessionNote.NoteType.TREATMENT_PLAN]
            for name, value in [('client', appointment.client_id), ('therapist', appointment.therapist_id), ('appointment', appointment.pk)]:
                self.initial[name] = value
                self.fields[name].disabled = True
                self.fields[name].widget = forms.HiddenInput()
            self.fields['treatment_plan'].queryset = self.fields['treatment_plan'].queryset.filter(client_id=appointment.client_id)

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and self.instance.is_locked:
            raise forms.ValidationError("Locked clinical notes are read-only and cannot be changed.")
        # ModelForm validates the model before save(), so establish the lock timestamp now.
        if cleaned_data.get('is_locked') and not self.instance.locked_at:
            self.instance.locked_at = timezone.now()
        client = cleaned_data.get('client')
        treatment_plan = cleaned_data.get('treatment_plan')
        if client and treatment_plan and treatment_plan.client_id != client.pk:
            self.add_error('treatment_plan', 'Selected treatment plan must belong to the note client.')
        return cleaned_data

    def save(self, commit=True):
        note = super().save(commit=False)
        note.practice = self.practice
        if note.is_locked and not note.locked_at:
            note.locked_at = timezone.now()
        if not note.is_locked:
            note.locked_at = None
        if commit:
            note.full_clean()
            note.save()
            self.save_m2m()
        return note


class DiagnosisForm(forms.ModelForm):
    class Meta:
        model = Diagnosis
        fields = ['client', 'code', 'label', 'diagnosed_at', 'active', 'notes']
        widgets = {
            'diagnosed_at': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        if patient:
            self.fields['client'].initial = patient.pk
            self.initial['client'] = patient.pk
            self.fields['client'].disabled = True
        if practice:
            self.fields['client'].queryset = practice.clients.all()
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()

    def save(self, commit=True):
        diagnosis = super().save(commit=False)
        diagnosis.practice = self.practice
        if commit:
            diagnosis.full_clean()
            diagnosis.save()
            self.save_m2m()
        return diagnosis


class TreatmentPlanForm(forms.ModelForm):
    class Meta:
        model = TreatmentPlan
        fields = [
            'client',
            'therapist',
            'diagnoses',
            'title',
            'status',
            'goals',
            'objectives',
            'interventions',
            'start_date',
            'review_date',
            'completed_at',
        ]
        widgets = {
            'diagnoses': forms.CheckboxSelectMultiple,
            'goals': forms.Textarea(attrs={'rows': 5}),
            'objectives': forms.Textarea(attrs={'rows': 4}),
            'interventions': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'review_date': forms.DateInput(attrs={'type': 'date'}),
            'completed_at': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['therapist'].queryset = practice.therapists.select_related('user')
            client_id = self.data.get('client') if self.is_bound else (self.initial.get('client') or self.instance.client_id)
            allowed = Q(active=True)
            if self.instance.pk:
                allowed |= Q(treatment_plans=self.instance)
            diagnoses = practice.diagnoses.filter(allowed).distinct()
            if str(client_id or '').isascii() and str(client_id or '').isdigit() and len(str(client_id)) <= 18:
                diagnoses = diagnoses.filter(client_id=client_id)
            else:
                diagnoses = diagnoses.none()
            self.fields['diagnoses'].queryset = diagnoses
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['therapist'].queryset = self.fields['therapist'].queryset.none()
            self.fields['diagnoses'].queryset = self.fields['diagnoses'].queryset.none()

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        diagnoses = cleaned_data.get('diagnoses')
        if client and diagnoses:
            mismatched = [diagnosis.code for diagnosis in diagnoses if diagnosis.client_id != client.pk]
            if mismatched:
                self.add_error('diagnoses', 'Selected diagnoses must belong to the treatment plan client.')
        return cleaned_data

    def save(self, commit=True):
        plan = super().save(commit=False)
        plan.practice = self.practice
        if commit:
            plan.full_clean()
            plan.save()
            self.save_m2m()
        return plan
