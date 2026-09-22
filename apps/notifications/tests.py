from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.clients.models import Client
from apps.notifications.models import Notification
from apps.practices.models import Practice


class NotificationModelTests(TestCase):
    def test_notification_rejects_client_from_other_practice(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        other_practice = Practice.objects.create(name="Other Clinic")
        client = Client.objects.create(practice=other_practice, first_name="Ana", last_name="Perez")
        notification = Notification(
            practice=practice,
            client=client,
            subject="Appointment reminder",
            message="You have an upcoming appointment.",
        )

        with self.assertRaisesMessage(ValidationError, "same practice"):
            notification.full_clean()

    def test_notification_defaults_to_email_pending(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        notification = Notification(
            practice=practice,
            subject="Welcome",
            message="Welcome to NuviaMy.",
        )

        notification.full_clean()
        self.assertEqual(notification.channel, Notification.Channel.EMAIL)
        self.assertEqual(notification.status, Notification.Status.PENDING)
