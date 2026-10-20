from django import forms

from .contract_models import ClinicalContractBundle, PROVIDER_SIGNING_CONSENT

SIGNING_CONSENT = ('I have read the complete contract packet and intend to sign it electronically on behalf '
                   'of the identified practice. I am authorized to bind that practice. I understand that '
                   'this signature does not by itself authorize real patient data or activate clinical use.')


class ContractRequestForm(forms.Form):
    legal_name = forms.CharField(max_length=200, label='Practice legal name')
    legal_form = forms.CharField(max_length=120, label='Legal form or sole practitioner')
    address = forms.CharField(max_length=600, widget=forms.Textarea(attrs={'rows': 3}), label='Registered address and country')
    representative_name = forms.CharField(max_length=200, label='Authorized representative full name')
    representative_title = forms.CharField(max_length=200, label='Representative title')
    privacy_email = forms.EmailField(label='Monitored privacy and incident email')
    alternate_contact = forms.CharField(max_length=200, label='Alternate incident contact')
    jurisdiction = forms.CharField(max_length=300, label='Countries, states and clinical profession')
    patient_scope = forms.ChoiceField(choices=[('adults', 'Adults only'), ('minors', 'Adults and minors — additional review required')])
    hipaa_role = forms.ChoiceField(label='Practice HIPAA role', choices=[
        ('covered_entity', 'HIPAA covered entity'),
        ('business_associate', 'Business associate acting for another entity'),
        ('not_applicable', 'HIPAA not applicable — subject to review'),
    ])
    role_explanation = forms.CharField(max_length=600, widget=forms.Textarea(attrs={'rows': 3}),
        label='HIPAA role explanation or upstream entity and scope',
        help_text='Do not include patient information.')
    authority = forms.BooleanField(label='I am authorized to request these agreements for this practice.')


class ContractSignatureForm(forms.Form):
    bundle_digest = forms.CharField(max_length=64, widget=forms.HiddenInput)
    signer_name = forms.CharField(max_length=200, label='Type your full legal name')
    consent = forms.BooleanField(label=SIGNING_CONSENT)


class PublishContractBundleForm(forms.ModelForm):
    execute_as_provider = forms.BooleanField(required=True, label=PROVIDER_SIGNING_CONSENT)

    class Meta:
        model = ClinicalContractBundle
        exclude = ('provider_signer', 'digest', 'created_at')

    def clean_request(self):
        request = self.cleaned_data['request']
        latest = type(request).objects.filter(practice=request.practice).order_by('-created_at', '-pk').first()
        if latest.pk != request.pk:
            raise forms.ValidationError('Use the latest practice details when preparing a packet.')
        return request
