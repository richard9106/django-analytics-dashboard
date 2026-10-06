import uuid
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.models import AccountSecurity
from apps.accounts.security import requires_mfa
from apps.audit.models import AuditLog
from apps.audit.utils import get_audit_practice


class Command(BaseCommand):
    help = 'Reset staff MFA after documented, independent identity verification. Revokes all sessions.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--reason', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        reason = options['reason'].strip()
        if not reason or len(reason) > 240:
            raise CommandError('Provide a verification ticket/reference (1–240 characters).')
        user = get_user_model().objects.filter(username=options['username']).first()
        if not user or not requires_mfa(user):
            raise CommandError('An internal staff account is required.')
        AccountSecurity.objects.get_or_create(user=user)
        AccountSecurity.objects.filter(user=user).update(secret='', confirmed=False, last_counter=-1,
            recovery_hashes=[], failed_attempts=0, blocked_until=None, session_version=uuid.uuid4())
        practice = get_audit_practice(user)
        AuditLog.objects.create(practice=practice, action=AuditLog.Action.UPDATE,
            object_type='accounts.AccountSecurity', object_id=str(user.pk),
            metadata={'event': 'mfa_support_reset', 'verification_reference': reason})
        self.stdout.write('MFA reset completed; all existing sessions revoked. User must sign in and enroll again.')
