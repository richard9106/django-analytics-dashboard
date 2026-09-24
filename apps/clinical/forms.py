from django import forms
from django.utils import timezone

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
        widgets = {
            'content': forms.Textarea(attrs={'rows': 8}),
            'treatment_progress': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, **kwargs):
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

    def clean(self):
        cleaned_data = super().clean()
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

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
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
            self.fields['diagnoses'].queryset = practice.diagnoses.select_related('client').filter(active=True)
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
