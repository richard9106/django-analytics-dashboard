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
from apps.audit.utils import get_request_ip
from apps.clients.models import Client
from apps.clinical.models import SessionNote, TreatmentPlan
from apps.practices.models import Practice, TherapistProfile


@override_settings(MFA_REQUIRED=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuditProtectionTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Synthetic audit fixture')
        self.user = get_user_model().objects.create_user('synthetic-actor', password='Synthetic-password-42!')
        UserProfile.objects.create(user=self.user, practice=self.practice, role=UserProfile.Role.OWNER)
        self.event = AuditLog.objects.create(practice=self.practice, actor=self.user,
            action=AuditLog.Action.VIEW, object_type='synthetic.Record', metadata={'event': 'synthetic_access'})

    def test_model_and_bulk_mutations_rejected(self):
        for operation in (lambda: self.event.save(), lambda: self.event.delete(),
                          lambda: AuditLog.objects.filter(pk=self.event.pk).update(metadata={}),
                          lambda: AuditLog.objects.filter(pk=self.event.pk).delete(),
                          lambda: AuditLog.objects.bulk_update([self.event], ['metadata'])):
            with self.subTest(operation=operation):
                with self.assertRaises(ValidationError):
                    operation()
        self.event.refresh_from_db()
        self.assertEqual(self.event.metadata, {'event': 'synthetic_access'})

    def test_actor_snapshot_survives_account_rename(self):
        self.user.username = 'renamed-actor'
        self.user.save()
        self.event.refresh_from_db()
        self.assertEqual(self.event.actor_id_snapshot, self.user.pk)
        self.assertEqual(self.event.actor_username_snapshot, 'synthetic-actor')

    def test_actor_and_practice_cannot_delete_evidence(self):
        for obj in (self.user, self.practice):
            with self.assertRaises(ProtectedError):
                obj.delete()
        self.assertTrue(AuditLog.objects.filter(pk=self.event.pk).exists())

    def test_bulk_insert_captures_identity(self):
        event = AuditLog(practice=self.practice, actor=self.user, action='view', object_type='synthetic.Bulk')
        AuditLog.objects.bulk_create(iter([event]), 1)
        event.refresh_from_db()
        self.assertEqual(event.actor_username_snapshot, self.user.username)

    def test_admin_is_read_only(self):
        self.user.is_staff = self.user.is_superuser = True
        request = RequestFactory().get('/admin/')
        request.user = self.user
        model_admin = admin.site._registry[AuditLog]
        self.assertTrue(model_admin.has_view_permission(request, self.event))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, self.event))
        self.assertFalse(model_admin.has_delete_permission(request, self.event))

    @skipUnless(connection.vendor == 'postgresql', 'PostgreSQL database guard')
    def test_sql_update_delete_and_truncate_are_rejected(self):
        for sql, params in [('UPDATE audit_auditlog SET metadata = %s WHERE id = %s', ['{}', self.event.pk]),
                            ('DELETE FROM audit_auditlog WHERE id = %s', [self.event.pk]),
                            ('TRUNCATE audit_auditlog', [])]:
            with self.subTest(sql=sql):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    with connection.cursor() as cursor:
                        if sql.startswith('TRUNCATE'):
                            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                        cursor.execute(sql, params)
        self.assertEqual(AuditLog.objects.get(pk=self.event.pk).metadata, {'event': 'synthetic_access'})

    @skipUnless(connection.vendor == 'postgresql', 'PostgreSQL database guard')
    def test_actor_snapshot_derived_by_database(self):
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO audit_auditlog (actor_id, action, object_type, object_id, metadata, user_agent, created_at, actor_username_snapshot) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING id',
                           [self.user.pk, 'view', 'synthetic.SQL', '', '{}', '', 'forged-name'])
            pk = cursor.fetchone()[0]
        event = AuditLog.objects.get(pk=pk)
        self.assertEqual(event.actor_username_snapshot, self.user.username)
        self.assertEqual(event.actor_id_snapshot, self.user.pk)

    def test_proxy_ip_is_validated_and_uses_appended_address(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='spoofed-prefix, 198.51.100.7')
        self.assertEqual(get_request_ip(request), '198.51.100.7')
        request.META['HTTP_X_FORWARDED_FOR'] = 'invalid'
        self.assertIsNone(get_request_ip(request))

    def test_patient_detail_read_has_identifiers_without_content(self):
        patient = Client.objects.create(practice=self.practice, first_name='Synthetic-private-name', last_name='Fixture')
        self.client.force_login(self.user)
        response = self.client.get(reverse('clients:detail', args=[patient.pk]) + '?search=Sensitive-search-text')
        self.assertEqual(response.status_code, 200)
        event = AuditLog.objects.get(object_type='access.clients', action='view')
        self.assertEqual(event.object_id, str(patient.pk))
        self.assertEqual(event.practice_id, self.practice.pk)
        self.assertNotIn('Sensitive-search-text', str(event.metadata))
        self.assertNotIn('Synthetic-private-name', str(event.metadata))

    def test_cross_practice_detail_denial_is_logged_to_requesting_practice(self):
        other = Practice.objects.create(name='Other synthetic practice')
        patient = Client.objects.create(practice=other, first_name='Other', last_name='Fixture')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('clients:detail', args=[patient.pk])).status_code, 404)
        event = AuditLog.objects.get(object_type='access.clients', action='denied')
        self.assertEqual(event.practice_id, self.practice.pk)

    def test_role_permission_redirect_records_denial(self):
        UserProfile.objects.filter(user=self.user).update(role=UserProfile.Role.THERAPIST, permissions={'clinical': {'view': False}})
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('clinical:list')).status_code, 302)
        self.assertTrue(AuditLog.objects.filter(object_type='access.clinical', action='denied').exists())

    def test_platform_admin_read_and_login_are_logged_without_practice(self):
        user = get_user_model().objects.create_superuser('synthetic-platform', password='Synthetic-password-42!')
        self.client.force_login(user)
        self.assertTrue(AuditLog.objects.filter(actor=user, practice=None, action='login').exists())
        self.assertEqual(self.client.get('/admin/clinical/sessionnote/').status_code, 200)
        self.assertTrue(AuditLog.objects.filter(actor=user, practice=None, object_type='access.admin.clinical.SessionNote').exists())

    def test_invalid_primary_credentials_are_logged_without_attempted_username(self):
        response = self.client.post(reverse('login'), {'username': 'private-attempt@example.com', 'password': 'Secret-invalid-password'})
        self.assertEqual(response.status_code, 200)
        event = AuditLog.objects.get(actor=None, action='denied')
        self.assertNotIn('private-attempt', str(event.metadata))
        self.assertNotIn('Secret-invalid', str(event.metadata))

    @override_settings(MFA_REQUIRED=True)
    def test_mfa_redirect_does_not_record_a_successful_read(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('clinical:list')).status_code, 302)
        self.assertTrue(AuditLog.objects.filter(object_type='access.clinical', action='denied', metadata__reason='mfa_required').exists())
        self.assertFalse(AuditLog.objects.filter(object_type='access.clinical', action='view').exists())
