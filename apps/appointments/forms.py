from django import forms

from .models import Appointment


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'client',
            'therapist',
            'starts_at',
            'ends_at',
            'appointment_type',
            'status',
            'location',
            'meeting_url',
            'notes',
        ]
        widgets = {
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.fields['starts_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['ends_at'].input_formats = ['%Y-%m-%dT%H:%M']

        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['therapist'].queryset = practice.therapists.select_related('user')
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['therapist'].queryset = self.fields['therapist'].queryset.none()

    def save(self, commit=True):
        appointment = super().save(commit=False)
        appointment.practice = self.practice
        if commit:
            appointment.full_clean()
            appointment.save()
            self.save_m2m()
        return appointment
