from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile
from apps.telehealth.models import TelehealthRoom


class TelehealthRoomModelTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name="NuviaMy Wellness")
        user = get_user_model().objects.create_user(username="drsmith")
        self.therapist = TherapistProfile.objects.create(
            user=user,
            practice=self.practice,
            license_number="ABC123",
            license_state="CA",
        )
        self.client = Client.objects.create(practice=self.practice, first_name="Ana", last_name="Perez")
        starts_at = timezone.now() + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
            appointment_type=Appointment.AppointmentType.VIDEO,
        )

    def test_telehealth_room_accepts_video_appointment(self):
        room = TelehealthRoom(
            practice=self.practice,
            appointment=self.appointment,
            join_url="https://video.example.com/join/abc",
        )

        room.full_clean()

    def test_telehealth_room_rejects_non_video_appointment(self):
        self.appointment.appointment_type = Appointment.AppointmentType.IN_PERSON
        room = TelehealthRoom(
            practice=self.practice,
            appointment=self.appointment,
            join_url="https://video.example.com/join/abc",
        )

        with self.assertRaisesMessage(ValidationError, "video appointments"):
            room.full_clean()
