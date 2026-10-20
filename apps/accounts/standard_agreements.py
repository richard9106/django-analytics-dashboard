"""Published standard offer and immutable customer acceptance snapshots."""
import hashlib
import json
from pathlib import Path

from django import forms
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string

from .legal import TERMS_VERSION, PRIVACY_VERSION, legal_context

AGREEMENT_VERSION = '2026-10-20-standard-v1'
CONSENT = ('I am authorized to bind the identified practice. I have read and electronically accept '
           'the Terms of Use, Data Processing Agreement and Standard Processing Schedule, and the '
           'Business Associate Agreement where HIPAA applies. I acknowledge the Privacy Notice. '
           'These agreements cover the free trial and any subsequent subscription.')


def documents():
    directory = Path(__file__).parent / 'agreements' / '2026-10-20-v1'
    result = {name: (directory / f'{name}.txt').read_text() for name in ('dpa', 'baa', 'schedule')}
    context = legal_context(None)
    for name, template in [('terms', 'terms'), ('privacy', 'privacy_policy')]:
        result[name] = render_to_string(f'marketing/{template}.html', context)
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def offer_digest():
    return digest(documents())


class StandardAgreementForm(forms.Form):
    representative_name = forms.CharField(max_length=200, label='Your full legal name')
    legal_name = forms.CharField(max_length=200, label='Practice legal name or sole practitioner')
    registered_address = forms.CharField(max_length=600, label='Registered address and country', widget=forms.Textarea(attrs={'rows': 2}))
    representative_title = forms.CharField(max_length=200, label='Your title or role', initial='Practice owner')
    agreement_digest = forms.CharField(widget=forms.HiddenInput, max_length=64)
    accept_terms = forms.BooleanField(required=True, label=CONSENT,
        error_messages={'required': 'Accept the practice agreements to continue.'},
        widget=forms.CheckboxInput(attrs={'aria-describedby': 'terms-help terms-errors'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault('agreement_digest', offer_digest())

    def clean_agreement_digest(self):
        value = self.cleaned_data['agreement_digest']
        if value != offer_digest():
            raise forms.ValidationError('The agreements have changed. Reload this page and review them before accepting.')
        return value


@transaction.atomic
def accept_standard_agreement(user, practice, data):
    from .contract_models import StandardAgreementAcceptance
    from apps.audit.models import AuditLog
    from apps.practices.models import Practice
    Practice.objects.select_for_update().get(pk=practice.pk)
    existing = StandardAgreementAcceptance.objects.filter(practice=practice, version=AGREEMENT_VERSION).first()
    if existing:
        return existing
    texts = documents()
    if not data.get('accept_terms') or data.get('agreement_digest') != digest(texts):
        raise forms.ValidationError('Review and accept the current practice agreements.')
    customer = {key: data[key].strip() for key in ('legal_name', 'registered_address', 'representative_title')}
    customer.update(representative_name=data.get('representative_name', user.get_full_name()).strip(), email=user.email,
                    practice_id=practice.pk, user_id=user.pk)
    accepted_at = timezone.now()
    snapshot = {'accepted_at': accepted_at.isoformat(), 'version': AGREEMENT_VERSION, 'terms_version': TERMS_VERSION,
                'privacy_version': PRIVACY_VERSION, 'documents': texts, 'customer': customer,
                'provider': 'Richard Andres Marles Bonilla, trading as NuviaMy',
                'execution': 'Published provider offer expressly accepted electronically by the customer',
                'consent': CONSENT}
    acceptance = StandardAgreementAcceptance.objects.create(practice=practice, signer=user,
        version=AGREEMENT_VERSION, snapshot=snapshot, digest=digest(snapshot), created_at=accepted_at)
    AuditLog.objects.create(practice=practice, actor=user, action=AuditLog.Action.CREATE,
        object_type='service_agreement', object_id=str(acceptance.pk),
        metadata={'event': 'standard_agreements_accepted', 'terms_version': TERMS_VERSION,
                  'privacy_notice_version': PRIVACY_VERSION, 'agreement_version': AGREEMENT_VERSION,
                  'agreement_digest': acceptance.digest})
    return acceptance
