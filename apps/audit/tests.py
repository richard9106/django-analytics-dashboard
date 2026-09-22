from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.practices.models import Practice


class AuditLogModelTests(TestCase):
    def test_audit_log_records_actor_action_and_object(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        user = get_user_model().objects.create_user(username="admin")
        log = AuditLog.objects.create(
            practice=practice,
            actor=user,
            action=AuditLog.Action.VIEW,
            object_type="Client",
            object_id="123",
            metadata={"source": "test"},
        )

        self.assertEqual(str(log), "View Client")
        self.assertEqual(log.metadata["source"], "test")
