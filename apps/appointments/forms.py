from django import forms

from .models import Appointment, PracticeAvailabilityOverride, PracticeWorkingHour


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
        self.instance.practice = practice
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


class CalendarAvailabilityEditForm(forms.ModelForm):
    class Meta:
        model = PracticeAvailabilityOverride
        fields = ['date', 'is_available', 'starts_at', 'ends_at', 'note']
        labels = {'is_available': 'Available during these hours', 'starts_at': 'Start time', 'ends_at': 'End time'}
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'starts_at': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'ends_at': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # An edit changes one existing date, never a whole recurring series.
        self.fields['date'].disabled = True
        for field in ('starts_at', 'ends_at'):
            self.fields[field].input_formats = ['%H:%M']


class PracticeAvailabilityOverrideForm(forms.ModelForm):
    REPEAT_NONE = 'none'
    REPEAT_WEEKLY = 'weekly'
    REPEAT_MONTHLY = 'monthly'
    REPEAT_CHOICES = (
        (REPEAT_NONE, 'Only this date'),
        (REPEAT_WEEKLY, 'Repeat weekly'),
        (REPEAT_MONTHLY, 'Repeat monthly'),
    )

    repeat = forms.ChoiceField(choices=REPEAT_CHOICES, required=False, initial=REPEAT_NONE)
    repeat_count = forms.IntegerField(min_value=1, max_value=52, required=False, initial=1, label='Occurrences')
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='End date')

    class Meta:
        model = PracticeAvailabilityOverride
        fields = ['date', 'is_available', 'starts_at', 'ends_at', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'starts_at': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'ends_at': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }
        labels = {
            'is_available': 'Available during these hours',
            'starts_at': 'Start time',
            'ends_at': 'End time',
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        self.fields['starts_at'].input_formats = ['%H:%M']
        self.fields['ends_at'].input_formats = ['%H:%M']

    def clean(self):
        cleaned_data = super().clean()
        repeat = cleaned_data.get('repeat') or self.REPEAT_NONE
        repeat_count = cleaned_data.get('repeat_count') or 1
        start_date = cleaned_data.get('date')
        end_date = cleaned_data.get('end_date')
        if end_date and start_date and end_date < start_date:
            self.add_error('end_date', 'End date must be on or after the start date.')
        if end_date:
            cleaned_data['repeat'] = self.REPEAT_NONE
            cleaned_data['repeat_count'] = 1
        elif repeat == self.REPEAT_NONE:
            cleaned_data['repeat_count'] = 1
        elif repeat_count < 2:
            self.add_error('repeat_count', 'Use at least 2 occurrences when repeating availability.')
        return cleaned_data

    def save(self, commit=True):
        override = super().save(commit=False)
        override.practice = self.practice
        if commit:
            override.full_clean()
            override.save()
            self.save_m2m()
        return override
