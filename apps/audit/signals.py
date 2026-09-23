from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog
from .utils import log_audit_event


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    log_audit_event(request, AuditLog.Action.LOGIN, 'auth.User', user.pk, actor=user)


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    if user:
        log_audit_event(request, AuditLog.Action.LOGOUT, 'auth.User', user.pk, actor=user)
