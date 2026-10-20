import io
import json
import time
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction, IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.practices.models import Practice
from apps.audit.models import AuditLog
from .models import UserProfile
from .contract_forms import PublishContractBundleForm
from .contract_models import ClinicalContractRequest, ClinicalContractBundle, ClinicalContractSignature


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False,
                   STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ContractFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.practice = Practice.objects.create(name='Fictional contracts clinic')
        cls.owner = get_user_model().objects.create_user('contract-owner', email='owner@example.invalid', password='ContractTestPassword2026!')
        UserProfile.objects.create(user=cls.owner, practice=cls.practice, role=UserProfile.Role.OWNER)
        cls.operator = get_user_model().objects.create_superuser('contract-operator', 'operator@example.invalid', 'OperatorTestPassword2026!')

    def setUp(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session['security_auth_at'] = time.time()
        session.save()

    def details(self, **extra):
        return dict(legal_name='Fictional Clinic LLC', legal_form='LLC', address='123 Fictional Street, US',
                    representative_name='Fictional Owner', representative_title='Director',
                    privacy_email='privacy@example.invalid', alternate_contact='Fictional alternate',
                    jurisdiction='California, psychologist', patient_scope='adults', hipaa_role='covered_entity',
                    role_explanation='Fictional covered practice', authority=True, **extra)

    def submission(self):
        return ClinicalContractRequest.objects.create(practice=self.practice, requested_by=self.owner, details=self.details())

    def bundle(self, submission=None, version='packet-v1', **extra):
        return ClinicalContractBundle.objects.create(request=submission or self.submission(), version=version,
            dpa_text='Complete fictional DPA terms.', baa_text='Complete fictional BAA terms.',
            schedule_text='Complete fictional service scope.', provider_signer=self.operator,
            provider_name='Fictional Authorized Operator', provider_title='Operator', **extra)

    def sign(self, bundle, **extra):
        return self.client.post(reverse('clinical_contract_sign', args=[bundle.pk]),
            dict(bundle_digest=bundle.digest, signer_name='Fictional Owner', consent='on') | extra)

    def review(self, bundle):
        return self.client.get(reverse('clinical_contract_review', args=[bundle.pk]))

    def test_request_is_distinct_from_signature_and_idempotent(self):
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1'), 'Submit practice details')
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1'), '>Contracts</a>')
        for _ in range(2):
            self.assertRedirects(self.client.post(reverse('clinical_contracts'), self.details()), reverse('clinical_contracts'))
        self.assertEqual(ClinicalContractRequest.objects.count(), 1)
        self.assertEqual(ClinicalContractSignature.objects.count(), 0)
        self.assertEqual(AuditLog.objects.filter(metadata__event='contract_requested').count(), 1)
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1'), 'Awaiting preparation')

    def test_corrected_request_preserves_history_and_supersedes_unsigned_packet(self):
        bundle = self.bundle()
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1&revise=1'), 'Submit practice details')
        data = self.details(); data['legal_name'] = 'Corrected Fictional Clinic'
        data['request_revision'] = str(bundle.request_id)
        for _ in range(2):
            self.client.post(reverse('clinical_contracts'), data)
        self.assertEqual(ClinicalContractRequest.objects.count(), 2)
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1'), 'Awaiting preparation by NuviaMy.')
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1'), 'Superseded packet.')
        self.assertEqual(ClinicalContractRequest.objects.get(pk=bundle.request_id).details['legal_name'], 'Fictional Clinic LLC')
        self.review(bundle)
        self.sign(bundle)
        self.assertFalse(ClinicalContractSignature.objects.exists())
        self.assertContains(self.review(bundle), 'This packet has been superseded')

    def test_invalid_correction_remains_visible_without_mutating_request(self):
        submission = self.submission()
        data = self.details(); data['legal_name'] = ''; data['request_revision'] = str(submission.pk)
        response = self.client.post(reverse('clinical_contracts'), data)
        self.assertContains(response, 'This field is required')
        self.assertContains(response, 'Submit practice details')
        self.assertEqual(ClinicalContractRequest.objects.count(), 1)

    def test_authority_is_required(self):
        data = self.details(); data.pop('authority')
        response = self.client.post(reverse('clinical_contracts'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ClinicalContractRequest.objects.exists())

    def test_non_owner_roles_cannot_access_any_endpoint(self):
        bundle = self.bundle()
        for role in (UserProfile.Role.ADMIN, UserProfile.Role.THERAPIST, UserProfile.Role.CLIENT):
            with self.subTest(role=role):
                UserProfile.objects.filter(user=self.owner).update(role=role)
                for name in ('clinical_contract_review', 'clinical_contract_download'):
                    self.assertEqual(self.client.get(reverse(name, args=[bundle.pk])).status_code, 403)
                self.assertEqual(self.client.get(reverse('clinical_contracts') + '?custom=1').status_code, 403)
                self.assertEqual(self.sign(bundle).status_code, 403)
        self.assertFalse(ClinicalContractSignature.objects.exists())

    def test_other_practice_owner_cannot_read_download_or_sign_packet(self):
        bundle = self.bundle()
        other = Practice.objects.create(name='Other fictional clinic')
        UserProfile.objects.filter(user=self.owner).update(practice=other)
        for name in ('clinical_contract_review', 'clinical_contract_download'):
            self.assertEqual(self.client.get(reverse(name, args=[bundle.pk])).status_code, 404)
        self.assertEqual(self.sign(bundle).status_code, 404)

    def test_anonymous_redirects_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('clinical_contracts') + '?custom=1').status_code, 302)
        self.assertIn('/login/', self.client.get(reverse('clinical_contracts') + '?custom=1').url)

    def test_review_signature_receipt_and_immutability(self):
        bundle = self.bundle()
        self.assertContains(self.review(bundle), bundle.dpa_text)
        self.assertRedirects(self.sign(bundle), reverse('clinical_contract_review', args=[bundle.pk]))
        signature = ClinicalContractSignature.objects.get()
        self.assertEqual(signature.bundle_digest, bundle.calculate_digest())
        self.assertEqual(signature.signer_email, self.owner.email)
        self.assertContains(self.client.get(reverse('clinical_contracts') + '?custom=1'), 'Signed by both parties')
        self.assertContains(self.review(bundle), 'Clinical approval remains pending')
        self.sign(bundle)
        self.assertEqual(ClinicalContractSignature.objects.count(), 1)
        response = self.client.get(reverse('clinical_contract_download', args=[bundle.pk]))
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        with ZipFile(io.BytesIO(response.content)) as z:
            packet = json.loads(z.read('contract-packet.json'))
            receipt = json.loads(z.read('signature-receipt.json'))
            self.assertEqual(packet, bundle.payload())
            self.assertEqual(receipt['customer_signature']['bundle_digest_sha256'], bundle.digest)
            self.assertEqual(z.read('dpa.txt').decode(), bundle.dpa_text)
        for obj in (bundle, signature, bundle.request):
            with self.assertRaises(ValidationError): obj.save()
            with self.assertRaises(ValidationError): obj.delete()
            with self.assertRaises(ValidationError): type(obj).objects.filter(pk=obj.pk).update(created_at=obj.created_at)
            with self.assertRaises(ValidationError): type(obj).objects.filter(pk=obj.pk).delete()
        self.assertEqual(AuditLog.objects.filter(metadata__event='contract_customer_signed').count(), 1)

    def test_signature_requires_review_and_consent_and_matching_digest_and_name(self):
        bundle = self.bundle()
        self.sign(bundle)
        self.assertFalse(ClinicalContractSignature.objects.exists())
        self.review(bundle)
        for change in ({'consent': ''}, {'bundle_digest': 'a' * 64}, {'signer_name': 'Another person'}):
            self.assertEqual(self.sign(bundle, **change).status_code, 200)
            self.assertFalse(ClinicalContractSignature.objects.exists())

    def test_review_expires_and_new_version_invalidates_old_signing(self):
        bundle = self.bundle()
        self.review(bundle)
        session = self.client.session
        session['contract_review']['at'] = time.time() - 1801
        session.save()
        self.sign(bundle)
        self.assertFalse(ClinicalContractSignature.objects.exists())
        self.review(bundle)
        self.bundle(submission=bundle.request, version='packet-v2')
        self.sign(bundle)
        self.assertFalse(ClinicalContractSignature.objects.exists())

    def test_signing_requires_recent_authentication_even_without_totp(self):
        bundle = self.bundle()
        self.review(bundle)
        session = self.client.session; session['security_auth_at'] = 0; session.save()
        response = self.sign(bundle)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('security_reauthenticate'), response.url)
        self.assertIn('next=', response.url)
        self.assertFalse(ClinicalContractSignature.objects.exists())

    def test_packets_cannot_publish_unfinished_templates_or_missing_baa(self):
        submission = self.submission()
        for field, value in (('schedule_text', 'Scope [PENDING]'), ('dpa_text', 'Signature: ____________________'), ('baa_text', '')):
            data = dict(request=submission, version='v', dpa_text='DPA', baa_text='BAA', schedule_text='Schedule',
                        provider_signer=self.operator, provider_name='Operator', provider_title='Operator')
            data[field] = value
            with self.assertRaises(ValidationError): ClinicalContractBundle.objects.create(**data)
        form = PublishContractBundleForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('execute_as_provider', form.errors)

    def test_optional_baa_requires_reviewed_non_hipaa_role_and_text_is_escaped(self):
        details = self.details(); details['hipaa_role'] = 'not_applicable'
        submission = ClinicalContractRequest.objects.create(practice=self.practice, requested_by=self.owner, details=details)
        bundle = ClinicalContractBundle.objects.create(request=submission, version='non-hipaa-v1',
            dpa_text='<script>fictional()</script>', baa_text='', schedule_text='Complete scope',
            provider_signer=self.operator, provider_name='Operator', provider_title='Operator')
        response = self.review(bundle)
        self.assertContains(response, '&lt;script&gt;fictional()&lt;/script&gt;')
        self.assertNotContains(response, '<script>fictional()</script>')
        self.assertNotContains(response, '<h2>HIPAA Business Associate Agreement</h2>')

    def test_staff_with_model_permissions_cannot_publish_or_view_provider_evidence(self):
        from django.contrib.auth.models import Permission
        staff = get_user_model().objects.create_user('contract-staff', is_staff=True)
        staff.user_permissions.set(Permission.objects.filter(content_type__app_label='accounts'))
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('admin:accounts_clinicalcontractbundle_add')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:accounts_clinicalcontractrequest_changelist')).status_code, 403)

    def test_admin_requires_provider_execution_and_captures_actor(self):
        submission = self.submission()
        url = reverse('admin:accounts_clinicalcontractbundle_add')
        self.client.force_login(self.operator)
        session = self.client.session; session['security_auth_at'] = time.time(); session.save()
        payload = dict(request=submission.pk, version='admin-packet-v1', dpa_text='Complete DPA',
                       baa_text='Complete BAA', schedule_text='Complete scope',
                       provider_name='Fictional Operator', provider_title='Operator', _save='Save')
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        self.assertFalse(ClinicalContractBundle.objects.exists())
        self.assertEqual(self.client.post(url, payload | {'execute_as_provider': 'on'}).status_code, 302)
        bundle = ClinicalContractBundle.objects.get()
        self.assertEqual(bundle.provider_signer, self.operator)
        self.assertEqual(bundle.digest, bundle.calculate_digest())
        self.assertEqual(AuditLog.objects.filter(metadata__event='contract_provider_signed').count(), 1)

    def test_contracts_available_after_trial_expiry_without_enabling_clinical_use(self):
        from datetime import timedelta
        from django.utils import timezone
        self.practice.subscription_required = True
        self.practice.free_trial_ends_at = timezone.now() - timedelta(days=1)
        self.practice.save()
        self.assertEqual(self.client.get(reverse('clinical_contracts') + '?custom=1').status_code, 200)
        self.assertEqual(self.client.post(reverse('clinical_contracts'), self.details()).status_code, 302)
        from apps.billing.access import subscription_access
        self.assertEqual(subscription_access(self.practice)['mode'], 'readonly')

    def test_csrf_is_required_for_signatures(self):
        from django.test import Client
        bundle = self.bundle()
        client = Client(enforce_csrf_checks=True); client.force_login(self.owner)
        self.assertEqual(client.post(reverse('clinical_contract_sign', args=[bundle.pk]), {}).status_code, 403)

    def test_database_rejects_direct_evidence_mutation(self):
        if connection.vendor != 'postgresql': self.skipTest('PostgreSQL trigger enforcement')
        bundle = self.bundle()
        self.review(bundle); self.sign(bundle)
        for table in ('accounts_clinicalcontractrequest', 'accounts_clinicalcontractbundle', 'accounts_clinicalcontractsignature'):
            for sql in (f'UPDATE {table} SET created_at = created_at', f'DELETE FROM {table}', f'TRUNCATE {table} CASCADE'):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                        cursor.execute(sql)


from apps.audit.testing import ProtectedRecordsTransactionTestCase


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False)
class ConcurrentContractSignatureTests(ProtectedRecordsTransactionTestCase):
    def test_same_packet_can_be_signed_only_once_across_workers(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL row locks required')
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.test import Client
        practice = Practice.objects.create(name='Concurrent fictional practice')
        owner = get_user_model().objects.create_user('concurrent-contract-owner', email='owner@example.invalid')
        UserProfile.objects.create(user=owner, practice=practice, role=UserProfile.Role.OWNER)
        operator = get_user_model().objects.create_superuser('concurrent-contract-operator', 'operator@example.invalid', None)
        submission = ClinicalContractRequest.objects.create(practice=practice, requested_by=owner,
            details={'hipaa_role': 'covered_entity', 'representative_name': 'Fictional Owner', 'representative_title': 'Owner'})
        bundle = ClinicalContractBundle.objects.create(request=submission, version='concurrent-v1',
            dpa_text='DPA', baa_text='BAA', schedule_text='Schedule', provider_signer=operator,
            provider_name='Fictional Operator', provider_title='Operator')
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(owner)
            session = client.session
            session['security_auth_at'] = time.time()
            session['contract_review'] = {'bundle': str(bundle.pk), 'digest': bundle.digest, 'at': time.time()}
            session.save()
        barrier = Barrier(2)

        def attempt(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(reverse('clinical_contract_sign', args=[bundle.pk]),
                    {'bundle_digest': bundle.digest, 'signer_name': 'Fictional Owner', 'consent': 'on'}).status_code
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(attempt, clients)), [302, 302])
        self.assertEqual(ClinicalContractSignature.objects.count(), 1)
        self.assertEqual(AuditLog.objects.filter(metadata__event='contract_customer_signed').count(), 1)
