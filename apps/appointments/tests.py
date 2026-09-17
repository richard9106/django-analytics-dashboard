from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile


class AppointmentModelTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name="Nuvia Wellness")
        self.user = get_user_model().objects.create_user(username="drsmith")
        self.therapist = TherapistProfile.objects.create(
            user=self.user,
            practice=self.practice,
            license_number="ABC123",
            license_state="CA",
        )
        self.client = Client.objects.create(
            practice=self.practice,
            primary_therapist=self.therapist,
            first_name="Ana",
            last_name="Perez",
        )
        self.starts_at = timezone.now() + timedelta(days=1)
        self.ends_at = self.starts_at + timedelta(minutes=50)

    def build_appointment(self, **overrides):
        data = {
            "practice": self.practice,
            "client": self.client,
            "therapist": self.therapist,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
        }
        data.update(overrides)
        return Appointment(**data)

    def test_appointment_accepts_same_practice_client_and_therapist(self):
        appointment = self.build_appointment()

        appointment.full_clean()

    def test_appointment_rejects_end_before_start(self):
        appointment = self.build_appointment(
            ends_at=self.starts_at - timedelta(minutes=10),
        )

        with self.assertRaisesMessage(ValidationError, "The appointment must end after it starts."):
            appointment.full_clean()

    def test_appointment_rejects_client_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_client = Client.objects.create(
            practice=other_practice,
            first_name="Carlos",
            last_name="Rivera",
        )
        appointment = self.build_appointment(client=other_client)

        with self.assertRaisesMessage(ValidationError, "The client must belong to the same practice"):
            appointment.full_clean()

    def test_appointment_rejects_therapist_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_user = get_user_model().objects.create_user(username="othertherapist")
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="XYZ789",
            license_state="NY",
        )
        appointment = self.build_appointment(therapist=other_therapist)

        with self.assertRaisesMessage(ValidationError, "The therapist must belong to the same practice"):
            appointment.full_clean()

    def test_appointment_defaults_to_scheduled_and_not_synced(self):
        appointment = self.build_appointment()

        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertFalse(appointment.sync_enabled)
        self.assertEqual(appointment.sync_status, Appointment.SyncStatus.NOT_SYNCED)
        self.assertEqual(appointment.external_calendar_provider, Appointment.CalendarProvider.NONE)

    def test_appointment_can_store_google_calendar_metadata(self):
        appointment = self.build_appointment(
            sync_enabled=True,
            external_calendar_provider=Appointment.CalendarProvider.GOOGLE,
            external_calendar_id="primary",
            external_event_id="google-event-123",
            external_event_url="https://calendar.google.com/calendar/event?eid=abc123",
            sync_status=Appointment.SyncStatus.SYNCED,
        )

        appointment.full_clean()
        self.assertEqual(appointment.external_event_id, "google-event-123")

    def test_disabled_sync_cannot_be_marked_synced(self):
        appointment = self.build_appointment(
            sync_enabled=False,
            sync_status=Appointment.SyncStatus.SYNCED,
        )

        with self.assertRaisesMessage(ValidationError, "Disabled calendar sync cannot be marked"):
            appointment.full_clean()
