from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.clinical.models import SessionNote
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile


class SessionNoteModelTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name="NuviaMy Wellness")
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
        starts_at = timezone.now() + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

    def build_note(self, **overrides):
        data = {
            "practice": self.practice,
            "client": self.client,
            "therapist": self.therapist,
            "appointment": self.appointment,
            "note_type": SessionNote.NoteType.PROGRESS_NOTE,
            "content": "Client reported progress on treatment goals.",
        }
        data.update(overrides)
        return SessionNote(**data)

    def test_session_note_accepts_matching_practice_relationships(self):
        note = self.build_note()

        note.full_clean()

    def test_session_note_can_exist_without_appointment(self):
        note = self.build_note(appointment=None)

        note.full_clean()

    def test_session_note_rejects_client_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_client = Client.objects.create(
            practice=other_practice,
            first_name="Carlos",
            last_name="Rivera",
        )
        note = self.build_note(client=other_client, appointment=None)

        with self.assertRaisesMessage(ValidationError, "The client must belong to the same practice"):
            note.full_clean()

    def test_session_note_rejects_therapist_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_user = get_user_model().objects.create_user(username="othertherapist")
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="XYZ789",
            license_state="NY",
        )
        note = self.build_note(therapist=other_therapist, appointment=None)

        with self.assertRaisesMessage(ValidationError, "The therapist must belong to the same practice"):
            note.full_clean()

    def test_session_note_rejects_appointment_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_user = get_user_model().objects.create_user(username="othertherapist")
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="XYZ789",
            license_state="NY",
        )
        other_client = Client.objects.create(
            practice=other_practice,
            primary_therapist=other_therapist,
            first_name="Carlos",
            last_name="Rivera",
        )
        starts_at = timezone.now() + timedelta(days=2)
        other_appointment = Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        note = self.build_note(appointment=other_appointment)

        with self.assertRaisesMessage(ValidationError, "The appointment must belong to the same practice"):
            note.full_clean()

    def test_session_note_rejects_appointment_with_different_client(self):
        other_client = Client.objects.create(
            practice=self.practice,
            first_name="Lucia",
            last_name="Garcia",
        )
        note = self.build_note(client=other_client)

        with self.assertRaisesMessage(ValidationError, "The appointment client must match"):
            note.full_clean()

    def test_session_note_lock_sets_locked_at(self):
        note = self.build_note()

        note.lock()
        note.full_clean()

        self.assertTrue(note.is_locked)
        self.assertIsNotNone(note.locked_at)

    def test_unlocked_note_rejects_locked_at(self):
        note = self.build_note(locked_at=timezone.now(), is_locked=False)

        with self.assertRaisesMessage(ValidationError, "cannot have locked_at set unless it is locked"):
            note.full_clean()
