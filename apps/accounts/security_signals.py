import time
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import AccountSecurity


@receiver(user_logged_in)
def start_security_session(sender, request, user, **kwargs):
    state, _ = AccountSecurity.objects.get_or_create(user=user)
    now = time.time()
    request.session.cycle_key()
    request.session.update({
        'security_version': str(state.session_version),
        'security_started_at': now,
        'security_last_activity': now,
        'security_password_at': now,
        'security_auth_at': now,
    })
    for name in ('mfa_version', 'mfa_pending', 'mfa_codes', 'security_next'):
        request.session.pop(name, None)


@receiver(pre_save, sender=get_user_model())
def detect_activation_change(sender, instance, **kwargs):
    old = sender.objects.filter(pk=instance.pk).values('is_active').first() if instance.pk else None
    instance._security_activation_changed = bool(old and old['is_active'] != instance.is_active)


@receiver(post_save, sender=get_user_model())
def revoke_on_activation_change(sender, instance, **kwargs):
    if getattr(instance, '_security_activation_changed', False):
        AccountSecurity.objects.filter(user=instance).update(session_version=uuid.uuid4())
