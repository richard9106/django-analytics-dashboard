from django import forms

from .models import Appointment, PracticeWorkingHour


class AppointmentForm(forms.ModelForm):
    repeat_weekly_count = forms.IntegerField(
        min_value=1,
        max_value=52,
        required=False,
        label='Repeat weekly',
        help_text='Total number of weekly appointments to create, including this one.',
    )

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
        if self.instance.pk:
            self.fields.pop('repeat_weekly_count', None)
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


class PracticeWorkingHourForm(forms.ModelForm):
    class Meta:
        model = PracticeWorkingHour
        fields = ['weekday', 'starts_at', 'ends_at', 'active']
        widgets = {
            'starts_at': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'ends_at': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        self.fields['starts_at'].input_formats = ['%H:%M']
        self.fields['ends_at'].input_formats = ['%H:%M']

    def save(self, commit=True):
        working_hour = super().save(commit=False)
        working_hour.practice = self.practice
        if commit:
            working_hour.full_clean()
            working_hour.save()
            self.save_m2m()
        return working_hour
