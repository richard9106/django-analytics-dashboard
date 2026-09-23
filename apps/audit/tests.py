from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile


class AuditLogViewTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Nuvia Therapy')
        self.user = get_user_model().objects.create_user(username='owner', password='StrongPass123!')
        self.therapist = TherapistProfile.objects.create(
            user=self.user,
            practice=self.practice,
            license_number='LIC-123',
            license_state='CA',
        )
        UserProfile.objects.create(user=self.user, practice=self.practice, role=UserProfile.Role.OWNER)
        self.client_record = Client.objects.create(
            practice=self.practice,
            first_name='Maya',
            last_name='Johnson',
            email='maya@example.com',
        )

    def test_login_creates_audit_log(self):
        response = self.client.post(reverse('login'), {'username': 'owner', 'password': 'StrongPass123!'})

        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(action=AuditLog.Action.LOGIN)
        self.assertEqual(log.practice, self.practice)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.object_type, 'auth.User')

    def test_document_upload_and_download_create_audit_logs(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('documents:create'), {
            'client': self.client_record.pk,
            'document_type': 'consent',
            'title': 'Consent form',
            'visible_to_client': 'on',
            'description': '',
            'file': SimpleUploadedFile('consent.txt', b'signed', content_type='text/plain'),
        })

        self.assertRedirects(response, reverse('documents:list'))
        created_log = AuditLog.objects.get(action=AuditLog.Action.CREATE, object_type='documents.ClientDocument')
        self.assertEqual(created_log.metadata['client_id'], self.client_record.pk)

        response = self.client.get(reverse('documents:download', args=[created_log.object_id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.EXPORT, object_type='documents.ClientDocument').exists())

    def test_clinical_note_create_creates_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('clinical:create'), {
            'client': self.client_record.pk,
            'therapist': self.therapist.pk,
            'appointment': '',
            'note_type': 'progress_note',
            'content': 'Client reported progress.',
        })

        self.assertRedirects(response, reverse('clinical:list'))
        log = AuditLog.objects.get(action=AuditLog.Action.CREATE, object_type='clinical.SessionNote')
        self.assertEqual(log.metadata['client_id'], self.client_record.pk)

    def test_invoice_create_creates_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('billing:invoice_create'), {
            'client': self.client_record.pk,
            'appointment': '',
            'package': '',
            'invoice_number': 'INV-1001',
            'amount': Decimal('120.00'),
            'status': 'draft',
            'due_date': '',
            'paid_at': '',
            'notes': '',
        })

        self.assertRedirects(response, reverse('billing:list'))
        log = AuditLog.objects.get(action=AuditLog.Action.CREATE, object_type='billing.Invoice')
        self.assertEqual(log.metadata['client_id'], self.client_record.pk)
        self.assertEqual(log.metadata['invoice_number'], 'INV-1001')

    def test_portal_access_create_creates_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('portal_settings:portal_access_create'), {
            'client': self.client_record.pk,
            'username': 'maya.portal',
            'email': 'maya@example.com',
            'password': 'StrongPass123!',
            'is_active': 'on',
        })

        self.assertRedirects(response, reverse('portal_settings:portal_access'))
        log = AuditLog.objects.get(action=AuditLog.Action.CREATE, object_type='portal.ClientPortalAccess')
        self.assertEqual(log.metadata['client_id'], self.client_record.pk)
