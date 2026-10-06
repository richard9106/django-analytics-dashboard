from unittest import skipUnless

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.clients.models import Client
from apps.clinical.models import SessionNote, TreatmentPlan
from apps.practices.models import Practice, TherapistProfile


@override_settings(MFA_REQUIRED=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ClinicalProtectionTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Synthetic protection clinic')
        self.user = get_user_model().objects.create_user('synthetic-clinician')
        UserProfile.objects.create(user=self.user, practice=self.practice, role=UserProfile.Role.OWNER)
        self.therapist = TherapistProfile.objects.create(user=self.user, practice=self.practice)
        self.patient = Client.objects.create(practice=self.practice, first_name='Synthetic', last_name='Patient')
        self.plan = TreatmentPlan.objects.create(practice=self.practice, client=self.patient,
            therapist=self.therapist, title='Synthetic plan', goals='Synthetic goal')
        self.note = SessionNote.objects.create(practice=self.practice, client=self.patient,
            therapist=self.therapist, treatment_plan=self.plan, content='Original synthetic content')
        self.stale_note = SessionNote.objects.get(pk=self.note.pk)
        self.note.lock()
        self.note.save()

    def test_stale_instances_cannot_edit_or_delete_finalized_note(self):
        self.stale_note.content = 'Replacement'
        for operation in (self.stale_note.save, self.stale_note.delete):
            with self.assertRaises(ValidationError):
                operation()
        self.note.refresh_from_db()
        self.assertEqual(self.note.content, 'Original synthetic content')
        self.assertTrue(self.note.is_locked)

    def test_bulk_changes_and_unlocking_rejected(self):
        for operation in (lambda: SessionNote.objects.filter(pk=self.note.pk).update(is_locked=False),
                          lambda: SessionNote.objects.filter(pk=self.note.pk).delete(),
                          lambda: SessionNote.objects.bulk_update([self.stale_note], ['content'])):
            with self.assertRaises(ValidationError):
                operation()

    def test_mixed_batch_does_not_change_draft_when_finalized_note_present(self):
        draft = SessionNote.objects.create(practice=self.practice, client=self.patient, therapist=self.therapist, content='Draft')
        with self.assertRaises(ValidationError):
            SessionNote.objects.filter(pk__in=[draft.pk, self.note.pk]).update(content='Replacement')
        draft.refresh_from_db()
        self.assertEqual(draft.content, 'Draft')

    def test_parent_deletion_cannot_remove_clinical_history(self):
        for parent in (self.patient, self.therapist, self.practice, self.user, self.plan):
            with self.subTest(parent=type(parent).__name__), self.assertRaises(ProtectedError):
                parent.delete()
        self.assertTrue(SessionNote.objects.filter(pk=self.note.pk).exists())

    @skipUnless(connection.vendor == 'postgresql', 'PostgreSQL database guard')
    def test_sql_mutations_and_truncate_rejected(self):
        for sql, params in [('UPDATE clinical_sessionnote SET is_locked = FALSE WHERE id = %s', [self.note.pk]),
                            ('UPDATE clinical_sessionnote SET content = %s WHERE id = %s', ['Replacement', self.note.pk]),
                            ('DELETE FROM clinical_sessionnote WHERE id = %s', [self.note.pk]),
                            ('TRUNCATE clinical_sessionnote', [])]:
            with self.subTest(sql=sql), self.assertRaises(IntegrityError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                    cursor.execute(sql, params)
        self.note.refresh_from_db()
        self.assertEqual(self.note.content, 'Original synthetic content')

    def test_finalized_note_admin_disallows_change_and_delete(self):
        request = RequestFactory().get('/admin/')
        self.user.is_superuser = self.user.is_staff = True
        request.user = self.user
        model_admin = admin.site._registry[SessionNote]
        self.assertFalse(model_admin.has_change_permission(request, self.note))
        self.assertFalse(model_admin.has_delete_permission(request, self.note))

    def test_patient_and_referenced_plan_delete_return_retained_record(self):
        self.client.force_login(self.user)
        for route, obj in [('clients:delete', self.patient), ('clinical:treatment_plan_delete', self.plan)]:
            with self.subTest(route=route):
                response = self.client.post(reverse(route, args=[obj.pk]))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
        self.assertEqual(AuditLog.objects.filter(action='denied', metadata__reason='clinical_record_retained').count(), 2)

    def test_finalized_note_http_write_denied_and_audited(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('clinical:delete', args=[self.note.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(AuditLog.objects.filter(action='denied', object_type='access.clinical').exists())
        self.assertTrue(SessionNote.objects.filter(pk=self.note.pk).exists())
