from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'date_of_birth',
            'status',
            'primary_therapist',
            'insurance_provider',
            'insurance_member_id',
            'emergency_contact_name',
            'emergency_contact_phone',
            'address_line1',
            'address_line2',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice

        if practice:
            self.fields['primary_therapist'].queryset = practice.therapists.select_related('user')
        else:
            self.fields['primary_therapist'].queryset = self.fields['primary_therapist'].queryset.none()

    def save(self, commit=True):
        client = super().save(commit=False)
        client.practice = self.practice
        if commit:
            client.full_clean()
            client.save()
            self.save_m2m()
        return client
