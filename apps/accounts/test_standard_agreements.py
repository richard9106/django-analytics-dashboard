import io
import json
import time
from datetime import timedelta
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction, IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.practices.models import Practice
from apps.billing.models import PracticeSubscription
from .models import UserProfile
from .contract_models import StandardAgreementAcceptance
from .standard_agreements import offer_digest, digest, documents
from . import test_legal_acceptance


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False)
class StandardAgreementTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('standard-owner', email='owner@example.invalid', first_name='Test', last_name='Owner')
        self.practice = Practice.objects.create(name='Test practice', subscription_required=True,
            free_trial_started_at=timezone.now()-timedelta(days=31), free_trial_ends_at=timezone.now()-timedelta(days=1))
        UserProfile.objects.create(user=self.owner, practice=self.practice, role='owner')
        self.client.force_login(self.owner)
        session = self.client.session
        session['security_auth_at'] = time.time()
        session.save()

    def payload(self, **extra):
        return dict(legal_name='Test Clinic LLC', registered_address='123 Test St, CA, USA',
            representative_name='Test Owner', representative_title='Owner',
            accept_terms=True, agreement_digest=offer_digest()) | extra

    def accept(self):
        response = self.client.post(reverse('clinical_contracts'), self.payload())
        self.assertEqual(response.status_code, 302)
        return StandardAgreementAcceptance.objects.get()

    def test_existing_owner_accepts_once_even_after_trial_expiry(self):
        self.assertContains(self.client.get(reverse('clinical_contracts')), 'Accept your practice agreements')
        record = self.accept()
        self.client.post(reverse('clinical_contracts'), self.payload())
        self.assertEqual(StandardAgreementAcceptance.objects.count(), 1)
        self.assertEqual(record.digest, digest(record.snapshot))
        self.assertEqual(record.snapshot['accepted_at'], record.created_at.isoformat())
        self.assertFalse(PracticeSubscription.objects.exists())
        self.assertContains(self.client.get(reverse('clinical_contracts')), 'Download agreements and receipt')

    def test_missing_acceptance_and_stale_offer_cannot_create_evidence(self):
        for extra in ({'accept_terms': False}, {'agreement_digest': '0'*64}, {'registered_address': ''}, {'representative_name': ''}, {'agreement_digest': ''}):
            response = self.client.post(reverse('clinical_contracts'), self.payload(**extra))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(StandardAgreementAcceptance.objects.exists())

    def test_download_is_exact_snapshot_even_if_public_offer_changes(self):
        record = self.accept()
        with patch('apps.accounts.standard_agreements.documents', return_value={'dpa': 'Future text'}):
            response = self.client.get(reverse('standard_agreement_download', args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        with ZipFile(io.BytesIO(response.content)) as archive:
            receipt = json.loads(archive.read('acceptance.json'))
            self.assertEqual(receipt['sha256'], digest(receipt['snapshot']))
            for name, text in record.snapshot['documents'].items():
                ext = 'html' if name in ('terms', 'privacy') else 'txt'
                self.assertEqual(archive.read(f'{name}.{ext}').decode(), text)

    def test_download_is_tenant_scoped_and_owner_only(self):
        record = self.accept()
        self.owner.nuvia_profile.role = 'admin'
        self.owner.nuvia_profile.save()
        self.assertEqual(self.client.get(reverse('standard_agreement_download', args=[record.pk])).status_code, 403)
        other = get_user_model().objects.create_user('other-standard')
        UserProfile.objects.create(user=other, practice=Practice.objects.create(name='Other'), role='owner')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('standard_agreement_download', args=[record.pk])).status_code, 404)

    def test_acceptance_requires_recent_authentication(self):
        session = self.client.session
        session['security_auth_at'] = 0
        session.save()
        response = self.client.post(reverse('clinical_contracts'), self.payload())
        self.assertIn(reverse('security_reauthenticate'), response.url)
        self.assertFalse(StandardAgreementAcceptance.objects.exists())

    def test_evidence_cannot_be_updated_or_deleted(self):
        record = self.accept()
        for mutation in (lambda: record.save(), lambda: record.delete(),
                         lambda: StandardAgreementAcceptance.objects.update(version='altered'),
                         lambda: StandardAgreementAcceptance.objects.all().delete()):
            with self.assertRaises(ValidationError):
                mutation()
        if connection.vendor == 'postgresql':
            for statement in ('UPDATE accounts_standardagreementacceptance SET version=\'altered\'',
                              'DELETE FROM accounts_standardagreementacceptance',
                              'TRUNCATE accounts_standardagreementacceptance'):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                        cursor.execute(statement)

    def test_public_offer_contains_complete_documents_without_placeholders(self):
        self.client.logout()
        response = self.client.get(reverse('standard_agreement_offer'))
        self.assertContains(response, 'NuviaMy Standard Processing Schedule')
        self.assertContains(response, 'Real client records')
        for text in documents().values():
            self.assertNotIn('[CUSTOMER', text)
            self.assertNotIn('________________', text)

    def test_signup_records_contracts_atomically_and_stale_form_creates_nothing(self):
        self.client.logout()
        data = test_legal_acceptance.LegalAcceptanceTests().payload()
        response = self.client.post(reverse('signup'), data | {'agreement_digest': '0'*64})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(email=data['email']).exists())
        response = self.client.post(reverse('signup'), data)
        self.assertEqual(response.status_code, 302)
        record = StandardAgreementAcceptance.objects.get()
        self.assertEqual(record.snapshot['customer']['representative_name'], 'Fictional Owner')
        practice = record.practice
        self.assertEqual(practice.free_trial_ends_at-practice.free_trial_started_at, timedelta(days=30))

    def test_trial_migration_extends_only_standard_fifteen_day_trials(self):
        from importlib import import_module
        from django.apps import apps
        migration = import_module('apps.practices.migrations.0011_extend_standard_trials_to_thirty_days')
        started = timezone.now()-timedelta(days=20)
        records = {}
        for name, days, kind in [('ordinary', 15, 'trial'), ('invitation', 365, 'early_access'),
                                  ('custom', 20, 'trial'), ('already_extended', 30, 'trial'), ('paid', 15, 'trial')]:
            records[name] = Practice.objects.create(name=name, free_access_kind=kind,
                free_trial_started_at=started, free_trial_ends_at=started+timedelta(days=days))
        PracticeSubscription.objects.create(practice=records['paid'], plan='solo', billing_period='monthly', status='active')
        migration.extend_standard_trials(apps, None)
        migration.extend_standard_trials(apps, None)
        for name, days in [('ordinary', 30), ('invitation', 365), ('custom', 20), ('already_extended', 30), ('paid', 15)]:
            records[name].refresh_from_db()
            self.assertEqual(records[name].free_trial_ends_at, started+timedelta(days=days))

    def test_dashboard_prompt_disappears_after_explicit_acceptance(self):
        self.assertContains(self.client.get(reverse('dashboard')), 'Accept your practice agreements')
        self.accept()
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Accept your practice agreements')


from apps.audit.testing import ProtectedRecordsTransactionTestCase


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False)
class ConcurrentStandardAgreementTests(ProtectedRecordsTransactionTestCase):
    def test_parallel_acceptances_produce_one_receipt(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL row locking required')
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.test import Client
        from apps.audit.models import AuditLog
        owner = get_user_model().objects.create_user('concurrent-standard', email='concurrent@example.invalid')
        practice = Practice.objects.create(name='Concurrent standard practice')
        UserProfile.objects.create(user=owner, practice=practice, role='owner')
        clients = [Client(), Client()]
        data = dict(legal_name='Test practice', registered_address='Test St, US', representative_name='Test Owner',
                    representative_title='Owner', accept_terms=True, agreement_digest=offer_digest())
        for client in clients:
            client.force_login(owner)
            session = client.session
            session['security_auth_at'] = time.time()
            session.save()
        barrier = Barrier(2)

        def attempt(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(reverse('clinical_contracts'), data).status_code
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(attempt, clients)), [302, 302])
        self.assertEqual(StandardAgreementAcceptance.objects.count(), 1)
        self.assertEqual(AuditLog.objects.filter(metadata__event='standard_agreements_accepted').count(), 1)
