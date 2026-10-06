"""Persistent authentication controls shared by every application worker."""
import uuid

from django.db import models
from apps.practices.fields import EncryptedTextField, get_fernet


class RequiredEncryptedTextField(EncryptedTextField):
    def get_prep_value(self, value):
        if value:
            get_fernet()  # Refuse plaintext storage, including in development.
        return super().get_prep_value(value)


class AccountSecurity(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='account_security')
    secret = RequiredEncryptedTextField(blank=True)
    confirmed = models.BooleanField(default=False)
    last_counter = models.BigIntegerField(default=-1)
    recovery_hashes = models.JSONField(default=list, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    session_version = models.UUIDField(default=uuid.uuid4, editable=False)


class RateLimitBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)
