from django import forms
from django.utils import timezone

from .models import SessionNote


class SessionNoteForm(forms.ModelForm):
    class Meta:
        model = SessionNote
        fields = [
            'client',
            'therapist',
            'appointment',
            'note_type',
            'content',
            'is_locked',
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 8}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice

        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['therapist'].queryset = practice.therapists.select_related('user')
            self.fields['appointment'].queryset = practice.appointments.select_related('client', 'therapist__user')
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['therapist'].queryset = self.fields['therapist'].queryset.none()
            self.fields['appointment'].queryset = self.fields['appointment'].queryset.none()

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
