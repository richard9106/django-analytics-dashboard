from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
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


class SessionNoteViewTests(TestCase):
    def create_practice_user(self, username="drsmith", practice_name="NuviaMy Wellness"):
        user = get_user_model().objects.create_user(
            username=username,
            password="StrongPass123!",
            first_name="Laura",
            last_name="Smith",
        )
        practice = Practice.objects.create(name=practice_name)
        therapist = TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number=f"{username}-12345",
            license_state="CA",
        )
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(
            practice=practice,
            primary_therapist=therapist,
            first_name="Maya",
            last_name="Johnson",
        )
        starts_at = timezone.now() + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        return user, practice, therapist, client, appointment

    def note_payload(self, therapist, client, appointment=None, **overrides):
        data = {
            "client": client.pk,
            "therapist": therapist.pk,
            "appointment": appointment.pk if appointment else "",
            "note_type": SessionNote.NoteType.PROGRESS_NOTE,
            "content": "Client reported improved sleep and lower anxiety.",
        }
        data.update(overrides)
        return data

    def test_note_list_requires_login(self):
        response = self.client.get(reverse("clinical:list"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('clinical:list')}")

    def test_note_create_requires_login(self):
        response = self.client.get(reverse("clinical:create"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('clinical:create')}")

    def test_note_list_is_scoped_to_user_practice_and_shows_modals(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            appointment=appointment,
            note_type=SessionNote.NoteType.PROGRESS_NOTE,
            content="Visible clinical content.",
        )
        SessionNote.objects.create(
            practice=other_practice,
            therapist=other_therapist,
            client=other_client,
            note_type=SessionNote.NoteType.GENERAL_NOTE,
            content="Hidden clinical content.",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible clinical content")
        self.assertNotContains(response, "Hidden clinical content")
        self.assertContains(response, 'id="note-create-modal"')
        self.assertContains(response, f'id="note-modal-{note.pk}"')
        self.assertContains(response, reverse("clinical:edit", args=[note.pk]))

    def test_note_create_saves_to_user_practice(self):
        user, practice, therapist, client, appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:create"),
            self.note_payload(therapist, client, appointment),
        )

        self.assertRedirects(response, reverse("clinical:list"))
        note = SessionNote.objects.get()
        self.assertEqual(note.practice, practice)
        self.assertEqual(note.client, client)
        self.assertEqual(note.therapist, therapist)

    def test_note_create_rejects_client_from_another_practice(self):
        user, _practice, therapist, _client, _appointment = self.create_practice_user()
        _other_user, _other_practice, _other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:create"),
            self.note_payload(therapist, other_client),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(SessionNote.objects.count(), 0)

    def test_note_update_saves_and_locks_note(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            appointment=appointment,
            note_type=SessionNote.NoteType.GENERAL_NOTE,
            content="Draft note.",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:edit", args=[note.pk]),
            self.note_payload(
                therapist,
                client,
                appointment,
                note_type=SessionNote.NoteType.TREATMENT_PLAN,
                content="Locked treatment plan.",
                is_locked="on",
            ),
        )

        self.assertRedirects(response, reverse("clinical:list"))
        note.refresh_from_db()
        self.assertEqual(note.note_type, SessionNote.NoteType.TREATMENT_PLAN)
        self.assertTrue(note.is_locked)
        self.assertIsNotNone(note.locked_at)

    def test_note_update_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client, _appointment = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        note = SessionNote.objects.create(
            practice=other_practice,
            therapist=other_therapist,
            client=other_client,
            content="Hidden note.",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:edit", args=[note.pk]))

        self.assertEqual(response.status_code, 404)

    def test_note_delete_removes_note(self):
        user, practice, therapist, client, _appointment = self.create_practice_user()
        note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            content="Delete me.",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:delete", args=[note.pk]))

        self.assertRedirects(response, reverse("clinical:list"))
        self.assertEqual(SessionNote.objects.count(), 0)

    def test_note_delete_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client, _appointment = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        note = SessionNote.objects.create(
            practice=other_practice,
            therapist=other_therapist,
            client=other_client,
            content="Hidden note.",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:delete", args=[note.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(SessionNote.objects.count(), 1)
