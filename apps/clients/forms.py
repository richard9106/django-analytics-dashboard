from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'first_name',
            'last_name',
            'profile_photo',
            'email',
            'phone',
            'date_of_birth',
            'status',
            'primary_therapist',
            'billing_type', 'insurance_payer', 'insurance_state', 'insurance_copay',
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

        from apps.billing.insurance import available_payers
        from apps.billing.models import InsurancePayer
        from django.db.models import Q
        payers = available_payers(practice)
        if self.instance.pk and self.instance.insurance_payer_id:
            payers = InsurancePayer.objects.filter(Q(pk__in=payers.values('pk')) | Q(pk=self.instance.insurance_payer_id))
        self.fields['insurance_payer'].queryset = payers
        self.fields['billing_type'].required = False
        self.fields['insurance_provider'].label = 'Legacy / reference insurance name'
        self.fields['insurance_copay'].label = 'Expected client share per session (USD)'
        if practice:
            self.fields['primary_therapist'].queryset = practice.therapists.select_related('user')
        else:
            self.fields['primary_therapist'].queryset = self.fields['primary_therapist'].queryset.none()

    def clean(self):
        data = super().clean()
        data['billing_type'] = data.get('billing_type') or 'self_pay'
        payer = data.get('insurance_payer')
        from apps.billing.insurance import available_payers
        if payer and payer.pk != self.instance.insurance_payer_id and not available_payers(self.practice).filter(pk=payer.pk).exists():
            self.add_error('insurance_payer', 'Enable this payer in Insurance settings first.')
        if data['billing_type'] == 'insurance' and not payer:
            self.add_error('insurance_payer', 'Choose an enabled insurance payer.')
        state = (data.get('insurance_state') or '').upper()
        if state and (len(state) != 2 or not state.isascii() or not state.isalpha()):
            self.add_error('insurance_state', 'Use a two-letter US state code.')
        data['insurance_state'] = state
        if payer:
            data['insurance_provider'] = payer.name
        return data

    def save(self, commit=True):
        client = super().save(commit=False)
        client.practice = self.practice
        if commit:
            client.full_clean()
            client.save()
            self.save_m2m()
        return client
