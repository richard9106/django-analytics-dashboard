from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.clinical.models import Diagnosis, SessionNote, TreatmentPlan
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

    def test_session_note_accepts_matching_treatment_plan(self):
        plan = TreatmentPlan.objects.create(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            title="Anxiety care plan",
            goals="Reduce anxiety symptoms.",
        )
        note = self.build_note(treatment_plan=plan, treatment_progress="Practiced grounding skills.")

        note.full_clean()

    def test_session_note_rejects_treatment_plan_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_user = get_user_model().objects.create_user(username="otherplantherapist")
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="OTHER123",
            license_state="NY",
        )
        other_client = Client.objects.create(practice=other_practice, first_name="Kai", last_name="Lee")
        plan = TreatmentPlan.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            title="Hidden care plan",
            goals="Hidden goals.",
        )
        note = self.build_note(treatment_plan=plan)

        with self.assertRaisesMessage(ValidationError, "treatment plan must belong to the same practice"):
            note.full_clean()

    def test_session_note_rejects_treatment_plan_for_different_client(self):
        other_client = Client.objects.create(practice=self.practice, first_name="Lucia", last_name="Garcia")
        plan = TreatmentPlan.objects.create(
            practice=self.practice,
            client=other_client,
            therapist=self.therapist,
            title="Other client care plan",
            goals="Other goals.",
        )
        note = self.build_note(treatment_plan=plan)

        with self.assertRaisesMessage(ValidationError, "treatment plan client must match"):
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


class TreatmentPlanModelTests(TestCase):
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

    def test_diagnosis_rejects_client_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_client = Client.objects.create(practice=other_practice, first_name="Kai", last_name="Lee")
        diagnosis = Diagnosis(
            practice=self.practice,
            client=other_client,
            code="F41.1",
            label="Generalized anxiety disorder",
        )

        with self.assertRaisesMessage(ValidationError, "Diagnosis client must belong to the same practice"):
            diagnosis.full_clean()

    def test_treatment_plan_accepts_matching_practice_relationships(self):
        plan = TreatmentPlan(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            title="Anxiety care plan",
            goals="Reduce anxiety symptoms.",
            start_date=timezone.localdate(),
        )

        plan.full_clean()

    def test_treatment_plan_rejects_therapist_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_user = get_user_model().objects.create_user(username="othertherapist")
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="XYZ789",
            license_state="NY",
        )
        plan = TreatmentPlan(
            practice=self.practice,
            client=self.client,
            therapist=other_therapist,
            title="Mismatched plan",
            goals="Improve mood.",
            start_date=timezone.localdate(),
        )

        with self.assertRaisesMessage(ValidationError, "Treatment plan therapist must belong to the same practice"):
            plan.full_clean()

    def test_treatment_plan_rejects_review_date_before_start_date(self):
        today = timezone.localdate()
        plan = TreatmentPlan(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            title="Review plan",
            goals="Improve mood.",
            start_date=today,
            review_date=today - timedelta(days=1),
        )

        with self.assertRaisesMessage(ValidationError, "Review date cannot be before"):
            plan.full_clean()

    def test_treatment_plan_is_review_due_when_active_review_date_has_passed(self):
        plan = TreatmentPlan.objects.create(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            title="Due plan",
            goals="Review goals.",
            review_date=timezone.localdate(),
        )

        self.assertTrue(plan.is_review_due)

    def test_completed_treatment_plan_is_not_review_due(self):
        plan = TreatmentPlan.objects.create(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            title="Completed plan",
            status=TreatmentPlan.Status.COMPLETED,
            goals="Review goals.",
            review_date=timezone.localdate(),
        )

        self.assertFalse(plan.is_review_due)


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
            "treatment_plan": "",
            "note_type": SessionNote.NoteType.PROGRESS_NOTE,
            "content": "Client reported improved sleep and lower anxiety.",
            "treatment_progress": "",
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

    def test_note_create_links_treatment_plan_and_progress(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Anxiety care plan",
            goals="Reduce anxiety symptoms.",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:create"),
            self.note_payload(
                therapist,
                client,
                appointment,
                treatment_plan=plan.pk,
                treatment_progress="Client used breathing technique twice this week.",
            ),
        )

        self.assertRedirects(response, reverse("clinical:list"))
        note = SessionNote.objects.get()
        self.assertEqual(note.treatment_plan, plan)
        self.assertEqual(note.treatment_progress, "Client used breathing technique twice this week.")

    def test_note_create_rejects_treatment_plan_for_different_client(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        other_client = Client.objects.create(practice=practice, first_name="Other", last_name="Client")
        plan = TreatmentPlan.objects.create(
            practice=practice,
            client=other_client,
            therapist=therapist,
            title="Other client care plan",
            goals="Other goals.",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:create"),
            self.note_payload(therapist, client, appointment, treatment_plan=plan.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selected treatment plan must belong")
        self.assertEqual(SessionNote.objects.count(), 0)

    def test_note_create_rejects_treatment_plan_from_another_practice(self):
        user, _practice, therapist, client, appointment = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        plan = TreatmentPlan.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            title="Hidden care plan",
            goals="Hidden goals.",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:create"),
            self.note_payload(therapist, client, appointment, treatment_plan=plan.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(SessionNote.objects.count(), 0)

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


class TreatmentPlanViewTests(TestCase):
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
        return user, practice, therapist, client

    def diagnosis_payload(self, client, **overrides):
        data = {
            "client": client.pk,
            "code": "F41.1",
            "label": "Generalized anxiety disorder",
            "diagnosed_at": timezone.localdate().isoformat(),
            "active": "on",
            "notes": "Initial diagnosis.",
        }
        data.update(overrides)
        return data

    def plan_payload(self, therapist, client, diagnoses=None, **overrides):
        data = {
            "client": client.pk,
            "therapist": therapist.pk,
            "diagnoses": [diagnosis.pk for diagnosis in diagnoses or []],
            "title": "Anxiety care plan",
            "status": TreatmentPlan.Status.ACTIVE,
            "goals": "Reduce anxiety symptoms and improve sleep.",
            "objectives": "Practice grounding skills weekly.",
            "interventions": "CBT and psychoeducation.",
            "start_date": timezone.localdate().isoformat(),
            "review_date": "",
            "completed_at": "",
        }
        data.update(overrides)
        return data

    def test_treatment_plan_list_requires_login(self):
        response = self.client.get(reverse("clinical:treatment_plans"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('clinical:treatment_plans')}")

    def test_treatment_plan_list_is_scoped_to_user_practice(self):
        user, practice, therapist, client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Visible care plan",
            goals="Visible goals.",
        )
        TreatmentPlan.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            title="Hidden care plan",
            goals="Hidden goals.",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:treatment_plans"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible care plan")
        self.assertNotContains(response, "Hidden care plan")
        self.assertContains(response, 'id="plan-create-modal"')
        self.assertContains(response, 'id="diagnosis-create-modal"')

    def test_treatment_plan_list_highlights_due_reviews(self):
        user, practice, therapist, client = self.create_practice_user()
        TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Due care plan",
            goals="Review goals.",
            review_date=timezone.localdate(),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:treatment_plans"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review due")
        self.assertContains(response, "Complete review")

    def test_diagnosis_create_saves_to_user_practice(self):
        user, practice, _therapist, client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:diagnosis_create"), self.diagnosis_payload(client))

        self.assertRedirects(response, reverse("clinical:treatment_plans"))
        diagnosis = Diagnosis.objects.get()
        self.assertEqual(diagnosis.practice, practice)
        self.assertEqual(diagnosis.client, client)
        self.assertEqual(diagnosis.code, "F41.1")

    def test_diagnosis_create_rejects_client_from_another_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, _other_practice, _other_therapist, other_client = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:diagnosis_create"), self.diagnosis_payload(other_client))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Diagnosis.objects.count(), 0)

    def test_treatment_plan_create_saves_linked_diagnosis(self):
        user, practice, therapist, client = self.create_practice_user()
        diagnosis = Diagnosis.objects.create(
            practice=practice,
            client=client,
            code="F41.1",
            label="Generalized anxiety disorder",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:treatment_plan_create"),
            self.plan_payload(therapist, client, [diagnosis]),
        )

        self.assertRedirects(response, reverse("clinical:treatment_plans"))
        plan = TreatmentPlan.objects.get()
        self.assertEqual(plan.practice, practice)
        self.assertEqual(plan.client, client)
        self.assertEqual(plan.diagnoses.get(), diagnosis)

    def test_treatment_plan_create_rejects_diagnosis_for_different_client(self):
        user, practice, therapist, client = self.create_practice_user()
        other_client = Client.objects.create(practice=practice, first_name="Other", last_name="Client")
        diagnosis = Diagnosis.objects.create(
            practice=practice,
            client=other_client,
            code="F32.1",
            label="Major depressive disorder",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:treatment_plan_create"),
            self.plan_payload(therapist, client, [diagnosis]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selected diagnoses must belong")
        self.assertEqual(TreatmentPlan.objects.count(), 0)

    def test_treatment_plan_update_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        plan = TreatmentPlan.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            title="Hidden care plan",
            goals="Hidden goals.",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:treatment_plan_edit", args=[plan.pk]))

        self.assertEqual(response.status_code, 404)

    def test_treatment_plan_delete_removes_plan(self):
        user, practice, therapist, client = self.create_practice_user()
        plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Delete me",
            goals="Short term goals.",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:treatment_plan_delete", args=[plan.pk]))

        self.assertRedirects(response, reverse("clinical:treatment_plans"))
        self.assertEqual(TreatmentPlan.objects.count(), 0)

    def test_treatment_plan_complete_review_sets_next_review_date(self):
        user, practice, therapist, client = self.create_practice_user()
        plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Due care plan",
            status=TreatmentPlan.Status.REVIEW_DUE,
            goals="Review goals.",
            review_date=timezone.localdate(),
        )
        next_review = timezone.localdate() + timedelta(days=45)

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:treatment_plan_complete_review", args=[plan.pk]),
            {"next_review_date": next_review.isoformat()},
        )

        self.assertRedirects(response, reverse("clinical:treatment_plans"))
        plan.refresh_from_db()
        self.assertEqual(plan.status, TreatmentPlan.Status.ACTIVE)
        self.assertEqual(plan.review_date, next_review)

    def test_treatment_plan_complete_review_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        plan = TreatmentPlan.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            title="Hidden care plan",
            goals="Hidden goals.",
            review_date=timezone.localdate(),
        )

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:treatment_plan_complete_review", args=[plan.pk]))

        self.assertEqual(response.status_code, 404)
