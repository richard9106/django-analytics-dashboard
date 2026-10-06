from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
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

    def test_locked_note_cannot_be_saved_or_deleted(self):
        note = self.build_note()
        note.lock()
        note.save()

        note.content = "Attempted amendment."
        with self.assertRaisesMessage(ValidationError, "cannot be edited or unlocked"):
            note.save()
        with self.assertRaisesMessage(ValidationError, "cannot be deleted"):
            note.delete()

    def test_locked_note_gets_lock_timestamp_when_saved(self):
        note = self.build_note(is_locked=True)

        note.save()

        self.assertIsNotNone(note.locked_at)


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


@override_settings(MFA_REQUIRED=False)
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
        self.assertContains(response, 'class="notes-list clinical-note-tree"')
        self.assertContains(response, 'class="client-note-group"')
        self.assertContains(response, f'id="note-detail-modal-{note.pk}"')
        self.assertContains(response, f'id="note-modal-{note.pk}"')
        self.assertContains(response, reverse("clinical:edit", args=[note.pk]))
        self.assertEqual(len(response.context["note_groups"]), 1)
        self.assertEqual(response.context["note_groups"][0]["client"], client)
        self.assertEqual(response.context["note_groups"][0]["notes"], [note])

    def test_note_list_can_filter_by_client_type_status_session_and_date(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        other_client = Client.objects.create(practice=practice, first_name="Lucia", last_name="Garcia")
        other_appointment = Appointment.objects.create(
            practice=practice,
            therapist=therapist,
            client=other_client,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
        )
        visible_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            appointment=appointment,
            note_type=SessionNote.NoteType.PROGRESS_NOTE,
            content="Filtered visible note.",
            is_locked=True,
        )
        hidden_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=other_client,
            appointment=other_appointment,
            note_type=SessionNote.NoteType.GENERAL_NOTE,
            content="Filtered hidden note.",
        )
        filter_date = timezone.localdate() - timedelta(days=1)

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:list"), {
            "client": str(client.pk),
            "therapist": str(therapist.pk),
            "appointment": str(appointment.pk),
            "note_type": SessionNote.NoteType.PROGRESS_NOTE,
            "status": "locked",
            "date_from": filter_date.isoformat(),
            "date_to": timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Filtered visible note.")
        self.assertNotContains(response, "Filtered hidden note.")
        self.assertEqual(len(response.context["note_groups"]), 1)
        self.assertEqual(response.context["note_groups"][0]["client"], client)
        self.assertContains(response, 'value="locked" selected')
        self.assertContains(response, 'Apply filters')
        self.assertContains(response, reverse("clinical:list"))
        self.assertIn(visible_note, response.context["notes"])
        self.assertNotIn(hidden_note, response.context["notes"])

    def test_note_list_can_search_note_content_progress_client_and_plan(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        other_client = Client.objects.create(practice=practice, first_name="Lucia", last_name="Garcia")
        plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Grounding skills plan",
            goals="Practice grounding daily.",
        )
        content_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            appointment=appointment,
            note_type=SessionNote.NoteType.PROGRESS_NOTE,
            content="Client practiced paced breathing.",
        )
        progress_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            note_type=SessionNote.NoteType.GENERAL_NOTE,
            content="Follow up note.",
            treatment_progress="Used grounding between sessions.",
        )
        plan_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            treatment_plan=plan,
            note_type=SessionNote.NoteType.TREATMENT_PLAN,
            content="Reviewed care plan.",
        )
        client_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=other_client,
            note_type=SessionNote.NoteType.PROGRESS_NOTE,
            content="Client name search result.",
        )
        hidden_note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            note_type=SessionNote.NoteType.PROGRESS_NOTE,
            content="Medication review content.",
        )

        self.client.force_login(user)

        content_response = self.client.get(reverse("clinical:list"), {"q": "paced"})
        self.assertIn(content_note, content_response.context["notes"])
        self.assertNotIn(hidden_note, content_response.context["notes"])
        self.assertContains(content_response, 'value="paced"')

        progress_response = self.client.get(reverse("clinical:list"), {"q": "grounding"})
        self.assertIn(progress_note, progress_response.context["notes"])
        self.assertIn(plan_note, progress_response.context["notes"])
        self.assertNotIn(hidden_note, progress_response.context["notes"])

        client_response = self.client.get(reverse("clinical:list"), {"q": "Lucia"})
        self.assertIn(client_note, client_response.context["notes"])
        self.assertNotIn(content_note, client_response.context["notes"])

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

    def test_locked_note_is_read_only_and_has_no_edit_or_delete_controls(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            appointment=appointment,
            content="Finalized note.",
            is_locked=True,
        )

        self.client.force_login(user)
        list_response = self.client.get(reverse("clinical:list"))

        self.assertContains(list_response, "Finalized note.")
        self.assertContains(list_response, "Read-only clinical record")
        self.assertNotContains(list_response, reverse("clinical:edit", args=[note.pk]))
        self.assertNotContains(list_response, reverse("clinical:delete", args=[note.pk]))

        edit_response = self.client.get(reverse("clinical:edit", args=[note.pk]))
        self.assertEqual(edit_response.status_code, 404)

    def test_locked_note_post_update_and_delete_are_rejected(self):
        user, practice, therapist, client, appointment = self.create_practice_user()
        note = SessionNote.objects.create(
            practice=practice,
            therapist=therapist,
            client=client,
            appointment=appointment,
            content="Finalized note.",
            is_locked=True,
        )

        self.client.force_login(user)
        update_response = self.client.post(
            reverse("clinical:edit", args=[note.pk]),
            self.note_payload(therapist, client, appointment, content="Tampered note."),
        )
        delete_response = self.client.post(reverse("clinical:delete", args=[note.pk]))

        self.assertEqual(update_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        note.refresh_from_db()
        self.assertEqual(note.content, "Finalized note.")
        self.assertTrue(note.is_locked)

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


@override_settings(MFA_REQUIRED=False)
class TreatmentPlanViewTests(TestCase):
    def test_patient_diagnosis_dialog_keeps_validation_errors_and_entered_data(self):
        user, practice, therapist, client = self.create_practice_user()
        self.client.force_login(user)
        response = self.client.post(reverse('clinical:diagnosis_create') + f'?client={client.pk}',
            self.diagnosis_payload(client, label='', notes='Keep these notes', return_to_patient='1'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'clients/detail.html')
        self.assertEqual(response.context['diagnosis_modal_id'], 'diagnosis-create-modal')
        self.assertTrue(response.context['diagnosis_create_form'].errors)
        self.assertContains(response, 'Keep these notes')
        self.assertContains(response, 'data-diagnosis-errors')
        self.assertNotContains(response, 'name="client"')
        self.assertEqual(Diagnosis.objects.count(), 0)

    def test_patient_diagnosis_edit_dialog_keeps_errors_and_preserves_record(self):
        user, practice, therapist, client = self.create_practice_user()
        diagnosis = Diagnosis.objects.create(practice=practice, client=client, code='F41.1', label='Existing')
        self.client.force_login(user)
        response = self.client.post(reverse('clinical:diagnosis_edit', args=[diagnosis.pk]),
            self.diagnosis_payload(client, label='', return_to_patient='1'))
        self.assertTemplateUsed(response, 'clients/detail.html')
        self.assertEqual(response.context['diagnosis_modal_id'], f'diagnosis-edit-{diagnosis.pk}')
        self.assertContains(response, 'checkbox-field diagnosis-checkbox')
        diagnosis.refresh_from_db()
        self.assertEqual(diagnosis.label, 'Existing')
        response = self.client.post(reverse('clinical:diagnosis_edit', args=[diagnosis.pk]),
            self.diagnosis_payload(client, label='Updated', return_to_patient='1'))
        self.assertRedirects(response, reverse('clients:detail', args=[client.pk]))
        diagnosis.refresh_from_db()
        self.assertEqual(diagnosis.label, 'Updated')

    def test_patient_record_contains_diagnoses_without_treatment_management_duplicates(self):
        user, practice, therapist, client = self.create_practice_user()
        own = Diagnosis.objects.create(practice=practice, client=client, code='F41.1', label='Patient diagnosis')
        other_client = Client.objects.create(practice=practice, first_name='Other', last_name='Patient')
        Diagnosis.objects.create(practice=practice, client=other_client, code='F32.1', label='Unrelated diagnosis')
        self.client.force_login(user)
        response = self.client.get(reverse('clients:detail', args=[client.pk]))
        self.assertContains(response, 'Patient diagnosis')
        self.assertNotContains(response, 'Unrelated diagnosis')
        self.assertContains(response, reverse('clinical:diagnosis_create') + f'?client={client.pk}')
        response = self.client.get(reverse('clinical:treatment_plans'))
        self.assertNotContains(response, 'diagnosis-create-modal')
        self.assertNotContains(response, 'Edit diagnosis')

    def test_patient_diagnosis_create_locks_client_and_returns_to_record(self):
        user, practice, therapist, client = self.create_practice_user()
        other = Client.objects.create(practice=practice, first_name='Other', last_name='Patient')
        self.client.force_login(user)
        url = reverse('clinical:diagnosis_create') + f'?client={client.pk}'
        page = self.client.get(url)
        self.assertTrue(page.context['form'].fields['client'].disabled)
        response = self.client.post(url, self.diagnosis_payload(other))
        self.assertRedirects(response, reverse('clients:detail', args=[client.pk]))
        self.assertEqual(Diagnosis.objects.get().client, client)

    def test_diagnosis_options_are_patient_and_practice_scoped(self):
        user, practice, therapist, client = self.create_practice_user()
        own = Diagnosis.objects.create(practice=practice, client=client, code='F41.1', label='Patient diagnosis')
        other = Client.objects.create(practice=practice, first_name='Other', last_name='Patient')
        Diagnosis.objects.create(practice=practice, client=other, code='F32.1', label='Other diagnosis')
        foreign_practice = Practice.objects.create(name='Foreign')
        foreign = Client.objects.create(practice=foreign_practice, first_name='Foreign', last_name='Patient')
        self.client.force_login(user)
        response = self.client.get(reverse('clinical:diagnosis_options', args=[client.pk]))
        self.assertEqual([row['id'] for row in response.json()['diagnoses']], [own.pk])
        self.assertEqual(self.client.get(reverse('clinical:diagnosis_options', args=[foreign.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('clinical:diagnosis_create'), {'client': foreign.pk}).status_code, 404)

    def test_plan_choices_preserve_linked_inactive_diagnosis_and_exclude_other_patients(self):
        from apps.clinical.forms import TreatmentPlanForm
        user, practice, therapist, client = self.create_practice_user()
        diagnosis = Diagnosis.objects.create(practice=practice, client=client, code='F41.1', label='Previous diagnosis', active=False)
        other = Client.objects.create(practice=practice, first_name='Other', last_name='Patient')
        foreign = Diagnosis.objects.create(practice=practice, client=other, code='F32.1', label='Other diagnosis')
        plan = TreatmentPlan.objects.create(practice=practice, client=client, therapist=therapist, title='Care', goals='Goals')
        plan.diagnoses.add(diagnosis)
        form = TreatmentPlanForm(instance=plan, practice=practice)
        self.assertEqual(list(form.fields['diagnoses'].queryset), [diagnosis])
        data = self.plan_payload(therapist, client, [diagnosis])
        form = TreatmentPlanForm(data, instance=plan, practice=practice)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(list(plan.diagnoses.all()), [diagnosis])

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
        self.assertNotContains(response, 'id="diagnosis-create-modal"')
        self.assertContains(response, 'aria-label="Treatment plans grouped by client"')
        self.assertContains(response, 'class="client-note-group"')
        self.assertContains(response, 'id="plan-detail-modal-')
        self.assertEqual(len(response.context["plan_groups"]), 1)
        self.assertEqual(response.context["plan_groups"][0]["client"], client)

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

    def test_treatment_plan_list_can_filter_by_client_therapist_diagnosis_status_and_review_date(self):
        user, practice, therapist, client = self.create_practice_user()
        other_client = Client.objects.create(practice=practice, first_name="Lucia", last_name="Garcia")
        diagnosis = Diagnosis.objects.create(
            practice=practice,
            client=client,
            code="F41.1",
            label="Generalized anxiety disorder",
        )
        other_diagnosis = Diagnosis.objects.create(
            practice=practice,
            client=other_client,
            code="F32.1",
            label="Major depressive disorder",
        )
        review_date = timezone.localdate() + timedelta(days=30)
        visible_plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Filtered care plan",
            status=TreatmentPlan.Status.ACTIVE,
            goals="Visible goals.",
            review_date=review_date,
        )
        visible_plan.diagnoses.add(diagnosis)
        hidden_plan = TreatmentPlan.objects.create(
            practice=practice,
            client=other_client,
            therapist=therapist,
            title="Hidden care plan",
            status=TreatmentPlan.Status.COMPLETED,
            goals="Hidden goals.",
            review_date=review_date + timedelta(days=60),
        )
        hidden_plan.diagnoses.add(other_diagnosis)

        self.client.force_login(user)
        response = self.client.get(reverse("clinical:treatment_plans"), {
            "client": str(client.pk),
            "therapist": str(therapist.pk),
            "diagnosis": str(diagnosis.pk),
            "status": TreatmentPlan.Status.ACTIVE,
            "review_from": timezone.localdate().isoformat(),
            "review_to": (review_date + timedelta(days=1)).isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Filtered care plan")
        self.assertNotContains(response, "Hidden care plan")
        self.assertEqual(len(response.context["plan_groups"]), 1)
        self.assertEqual(response.context["plan_groups"][0]["client"], client)
        self.assertContains(response, 'value="active" selected')
        self.assertContains(response, 'Filter treatment plans')
        self.assertIn(visible_plan, response.context["plans"])
        self.assertNotIn(hidden_plan, response.context["plans"])

    def test_treatment_plan_list_can_search_plan_and_diagnosis_text(self):
        user, practice, therapist, client = self.create_practice_user()
        diagnosis = Diagnosis.objects.create(
            practice=practice,
            client=client,
            code="F43.10",
            label="Post-traumatic stress disorder",
        )
        diagnosis_plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Trauma care plan",
            goals="Increase safety and stabilization.",
        )
        diagnosis_plan.diagnoses.add(diagnosis)
        objectives_plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Sleep care plan",
            goals="Improve sleep.",
            objectives="Practice nightmare rescripting weekly.",
        )
        hidden_plan = TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title="Mood care plan",
            goals="Track mood.",
        )

        self.client.force_login(user)

        diagnosis_response = self.client.get(reverse("clinical:treatment_plans"), {"q": "F43.10"})
        self.assertIn(diagnosis_plan, diagnosis_response.context["plans"])
        self.assertNotIn(hidden_plan, diagnosis_response.context["plans"])
        self.assertContains(diagnosis_response, 'F43.10')

        objective_response = self.client.get(reverse("clinical:treatment_plans"), {"q": "rescripting"})
        self.assertIn(objectives_plan, objective_response.context["plans"])
        self.assertNotIn(hidden_plan, objective_response.context["plans"])

    def test_diagnosis_create_saves_to_user_practice(self):
        user, practice, _therapist, client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("clinical:diagnosis_create"), self.diagnosis_payload(client))

        self.assertRedirects(response, reverse('clients:detail', args=[client.pk]))
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
        self.assertContains(response, "Select a valid choice")
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

    def test_treatment_plan_complete_review_rejects_invalid_next_review_date(self):
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

        self.client.force_login(user)
        response = self.client.post(
            reverse("clinical:treatment_plan_complete_review", args=[plan.pk]),
            {"next_review_date": "not-a-date"},
        )

        self.assertRedirects(response, reverse("clinical:treatment_plans"))
        plan.refresh_from_db()
        self.assertEqual(plan.status, TreatmentPlan.Status.REVIEW_DUE)
        self.assertEqual(plan.review_date, timezone.localdate())

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
