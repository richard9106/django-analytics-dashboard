"""Append-only contract evidence, independent of billing and clinical approval."""
import hashlib
import json
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


PROVIDER_SIGNING_CONSENT = (
    'I am authorized to bind NuviaMy and expressly sign and offer this complete packet electronically. '
    'I have checked the customer details, versions, provider contracts and the absence of unresolved placeholders. '
    'This action is permanent and does not grant clinical approval.'
)


class ContractEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Contract evidence cannot be changed.')

    def delete(self):
        raise ValidationError('Contract evidence cannot be deleted.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Contract evidence cannot be changed.')

    def bulk_create(self, objs, **kwargs):
        # Creation must run validation and capture the document digest.
        raise ValidationError('Create contract evidence individually.')


class ContractEvidence(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    objects = ContractEvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Contract evidence cannot be changed.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Contract evidence cannot be deleted.')


class ClinicalContractRequest(ContractEvidence):
    practice = models.ForeignKey('practices.Practice', on_delete=models.PROTECT, related_name='contract_requests')
    requested_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    details = models.JSONField()

    def __str__(self):
        return f'{self.practice} — contract request {self.pk}'


class ClinicalContractBundle(ContractEvidence):
    """Final texts offered and expressly executed by an authorized NuviaMy operator."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ClinicalContractRequest, on_delete=models.PROTECT, related_name='bundles')
    version = models.CharField(max_length=100, help_text='Unique packet reference, including document versions.')
    dpa_text = models.TextField(help_text='Complete customer-specific DPA, without template placeholders.')
    baa_text = models.TextField(blank=True, help_text='Complete BAA when applicable.')
    schedule_text = models.TextField(help_text='Complete customer-specific schedule and approved scope.')
    provider_signer = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    provider_name = models.CharField(max_length=200)
    provider_title = models.CharField(max_length=200)
    provider_consent = models.TextField(default=PROVIDER_SIGNING_CONSENT, editable=False)
    digest = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['request', 'version'], name='contract_request_version_unique')]

    def payload(self):
        return {
            'bundle_id': str(self.pk), 'version': self.version,
            'practice_id': self.request.practice_id, 'customer_details': self.request.details,
            'documents': {'dpa': self.dpa_text, 'baa': self.baa_text, 'schedule': self.schedule_text},
            'provider': {'user_id': self.provider_signer_id, 'name': self.provider_name,
                         'title': self.provider_title, 'consent': self.provider_consent, 'signed_at': self.created_at.isoformat()},
        }

    def calculate_digest(self):
        return hashlib.sha256(json.dumps(self.payload(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def clean(self):
        super().clean()
        if self.request_id:
            role = self.request.details.get('hipaa_role')
            if role != 'not_applicable' and not self.baa_text.strip():
                raise ValidationError({'baa_text': 'This request requires a completed BAA.'})
            if role == 'not_applicable' and self.baa_text.strip():
                raise ValidationError({'baa_text': 'Resolve the customer HIPAA role before adding a BAA.'})
        for field in ('dpa_text', 'baa_text', 'schedule_text'):
            value = getattr(self, field)
            if '[' in value or ']' in value or '________________' in value:
                raise ValidationError({field: 'Replace all template placeholders and signature blanks before publishing.'})

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.digest = self.calculate_digest()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.request.practice} — {self.version}'


class ClinicalContractSignature(ContractEvidence):
    bundle = models.OneToOneField(ClinicalContractBundle, on_delete=models.PROTECT, related_name='customer_signature')
    signer = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    signer_name = models.CharField(max_length=200)
    signer_email = models.EmailField()
    signer_title = models.CharField(max_length=200)
    bundle_digest = models.CharField(max_length=64)
    consent_text = models.TextField()

    def clean(self):
        super().clean()
        if self.bundle_id and (self.bundle_digest != self.bundle.digest or
                               self.bundle_digest != self.bundle.calculate_digest()):
            raise ValidationError('The contract digest does not match the reviewed documents.')


class StandardAgreementAcceptance(ContractEvidence):
    """Exact published offer, customer identity and explicit acceptance; never overwritten."""
    practice = models.ForeignKey('practices.Practice', on_delete=models.PROTECT, related_name='standard_agreements')
    signer = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    version = models.CharField(max_length=100)
    snapshot = models.JSONField()
    digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['practice', 'version'], name='standard_agreement_practice_version')]

    def clean(self):
        super().clean()
        from .standard_agreements import digest
        if self.digest != digest(self.snapshot):
            raise ValidationError('Agreement snapshot digest does not match.')
