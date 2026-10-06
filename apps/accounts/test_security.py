"""Security boundary tests use mandatory MFA, unlike isolated domain view tests."""
import time
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pyotp
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.practices.models import Practice
from apps.audit.testing import ProtectedRecordsTransactionTestCase
from .models import AccountSecurity, RateLimitBucket, UserProfile
from .security import (confirm_enrollment, decrypt_session_value, matching_counter,
                       new_recovery_codes, security_state, verify_factor)


@override_settings(DEBUG=True, MFA_REQUIRED=True, FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountSecurityTests(TestCase):
    def setUp(self):
        self.password = 'Test-only-password-42!'
        self.user = get_user_model().objects.create_user('security-owner', email='synthetic@example.com', password=self.password)
        self.practice = Practice.objects.create(name='Synthetic security fixture')
        UserProfile.objects.create(user=self.user, practice=self.practice, role=UserProfile.Role.OWNER)
        self.secret = pyotp.random_base32()
        self.client.force_login(self.user)
        self.state = security_state(self.user)

    def enrolled(self, client=None):
        self.state.secret = self.secret
        self.state.confirmed = True
        self.state.last_counter = int(time.time()) // 30 - 2
        self.codes = new_recovery_codes(self.state)
        self.state.save()
        client = client or self.client
        session = client.session
        session['mfa_version'] = str(self.state.session_version)
        session.save()
        return client

    def change_session(self, **values):
        session = self.client.session
        session.update(values)
        session.save()

    def test_password_login_requires_setup(self):
        self.client.logout()
        response = self.client.post(reverse('login'), {'username': self.user.email, 'password': self.password})
        self.assertRedirects(response, reverse('mfa_setup'), fetch_redirect_response=False)

    def test_primary_login_cannot_reach_clinical_export_or_admin(self):
        for url in ('/dashboard/', '/accounts/export/', '/admin/', '/accounts/security/'):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse('mfa_setup'), fetch_redirect_response=False)

    def test_enrolled_account_requires_challenge(self):
        self.enrolled()
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get('/dashboard/'), reverse('mfa_challenge'), fetch_redirect_response=False)

    def test_setup_encrypts_pending_secret_and_requires_password(self):
        response = self.client.get(reverse('mfa_setup'))
        self.assertEqual(response.status_code, 200)
        secret = decrypt_session_value(self.client.session['mfa_pending']['secret'])
        self.assertNotIn(secret, self.client.session['mfa_pending']['secret'])
        self.assertContains(response, 'data:image/png;base64,')
        response = self.client.post(reverse('mfa_setup'), {'password': 'wrong', 'code': pyotp.TOTP(secret).now()})
        self.assertEqual(response.status_code, 200)
        self.state.refresh_from_db()
        self.assertFalse(self.state.confirmed)
        self.assertEqual(self.state.failed_attempts, 1)

    def test_enrollment_codes_display_once_and_secret_encrypted_at_rest(self):
        self.client.get(reverse('mfa_setup'))
        secret = decrypt_session_value(self.client.session['mfa_pending']['secret'])
        old_key = self.client.session.session_key
        enrollment_code = pyotp.TOTP(secret).now()
        response = self.client.post(reverse('mfa_setup'), {'password': self.password, 'code': enrollment_code})
        self.assertRedirects(response, reverse('mfa_recovery_codes'), fetch_redirect_response=False)
        self.assertNotEqual(old_key, self.client.session.session_key)
        codes = decrypt_session_value(self.client.session['mfa_codes'])
        self.assertEqual(len(codes), 10)
        self.assertNotIn(codes[0], self.client.session['mfa_codes'])
        with connection.cursor() as cursor:
            cursor.execute('SELECT secret FROM accounts_accountsecurity WHERE user_id = %s', [self.user.pk])
            stored = cursor.fetchone()[0]
        self.assertNotIn(secret, stored)
        self.state.refresh_from_db()
        self.assertEqual(self.state.secret, secret)
        self.assertNotIn(codes[0].replace('-', ''), self.state.recovery_hashes)
        self.assertContains(self.client.get(reverse('mfa_recovery_codes')), codes[0])
        self.assertRedirects(self.client.get(reverse('mfa_recovery_codes')), reverse('security_settings'), fetch_redirect_response=False)
        self.assertFalse(verify_factor(self.user, enrollment_code))

    def test_setup_stale_version_cannot_overwrite_enrollment(self):
        version = str(self.state.session_version)
        AccountSecurity.objects.filter(pk=self.state.pk).update(session_version=uuid.uuid4())
        self.assertIsNone(confirm_enrollment(self.user, self.secret, pyotp.TOTP(self.secret).now(), self.password, version))

    def test_setup_requires_encryption_key(self):
        with override_settings(FIELD_ENCRYPTION_KEY=''):
            with self.assertRaisesMessage(ImproperlyConfigured, 'FIELD_ENCRYPTION_KEY'):
                self.state.secret = self.secret
                self.state.save()

    def test_totp_is_single_use(self):
        self.enrolled()
        code = pyotp.TOTP(self.secret).now()
        self.assertTrue(verify_factor(self.user, code))
        self.assertFalse(verify_factor(self.user, code))

    def test_totp_clock_window_and_ascii_validation(self):
        now = 1800000000
        with patch('apps.accounts.security.time.time', return_value=now):
            totp = pyotp.TOTP(self.secret)
            for offset in (-30, 0, 30):
                self.assertIsNotNone(matching_counter(self.secret, totp.at(now + offset)))
            self.assertIsNone(matching_counter(self.secret, totp.at(now + 60)))
            self.assertIsNone(matching_counter(self.secret, '１２３４５６'))
            self.assertIsNone(matching_counter(self.secret, '12345'))

    def test_recovery_code_consumed_once(self):
        self.enrolled()
        self.assertTrue(verify_factor(self.user, self.codes[0]))
        self.assertFalse(verify_factor(self.user, self.codes[0]))
        self.state.refresh_from_db()
        self.assertEqual(len(self.state.recovery_hashes), 9)

    def test_account_lockout_persists_across_sessions(self):
        self.enrolled()
        for _ in range(5):
            self.assertFalse(verify_factor(self.user, 'invalid'))
        self.assertFalse(verify_factor(self.user, self.codes[0]))
        self.state.refresh_from_db()
        self.assertEqual(self.state.failed_attempts, 5)
        self.assertGreater(self.state.blocked_until, timezone.now())
        AccountSecurity.objects.filter(pk=self.state.pk).update(blocked_until=timezone.now() - timedelta(seconds=1))
        self.assertTrue(verify_factor(self.user, self.codes[0]))
        self.state.refresh_from_db()
        self.assertEqual(self.state.failed_attempts, 0)
        self.assertIsNone(self.state.blocked_until)

    def test_wrong_password_does_not_consume_factor(self):
        self.enrolled()
        self.assertFalse(verify_factor(self.user, self.codes[0], password='wrong'))
        self.assertTrue(verify_factor(self.user, self.codes[0], password=self.password))

    def test_challenge_rotates_session_and_rejects_external_next(self):
        self.enrolled()
        self.client.force_login(self.user)
        self.change_session(security_next='https://attacker.invalid/')
        old_key = self.client.session.session_key
        response = self.client.post(reverse('mfa_challenge'), {'code': self.codes[0]})
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        self.assertNotEqual(old_key, self.client.session.session_key)

    def test_idle_timeout(self):
        self.enrolled()
        self.change_session(security_last_activity=time.time() - 901)
        self.assertRedirects(self.client.get('/accounts/security/'), '/login/?session_expired=1', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_absolute_timeout_despite_recent_activity(self):
        self.enrolled()
        self.change_session(security_started_at=time.time() - 28801, security_last_activity=time.time())
        self.assertEqual(self.client.post(reverse('security_session')).status_code, 401)

    def test_pending_challenge_timeout(self):
        self.change_session(security_password_at=time.time() - 601)
        self.assertRedirects(self.client.get(reverse('mfa_setup')), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_legacy_session_without_stamp_invalidated(self):
        session = self.client.session
        session.pop('security_version')
        session.save()
        self.assertRedirects(self.client.get('/dashboard/'), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_sensitive_export_requires_recent_reauthentication(self):
        self.enrolled()
        self.change_session(security_auth_at=time.time() - 301)
        response = self.client.get(reverse('practice_data_export'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('security_reauthenticate')))

    def test_profile_post_requires_recent_reauthentication(self):
        self.enrolled()
        self.change_session(security_auth_at=time.time() - 301)
        self.assertEqual(self.client.post(reverse('profile_settings')).status_code, 302)
        self.assertTrue(self.client.post(reverse('profile_settings')).url.startswith(reverse('security_reauthenticate')))

    def test_reauthentication_requires_both_factors(self):
        self.enrolled()
        url = reverse('security_reauthenticate') + '?next=/accounts/export/'
        self.assertEqual(self.client.post(url, {'password': 'wrong', 'code': self.codes[0]}).status_code, 200)
        response = self.client.post(url, {'password': self.password, 'code': self.codes[0]})
        self.assertRedirects(response, '/accounts/export/', fetch_redirect_response=False)

    def test_revocation_preserves_current_session_rejects_other_session(self):
        self.enrolled()
        other = Client()
        other.force_login(self.user)
        self.enrolled(other)
        response = self.client.post(reverse('security_settings'), {'password': self.password, 'code': self.codes[0], 'action': 'revoke_sessions'})
        self.assertRedirects(response, reverse('security_settings'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('security_settings')).status_code, 200)
        self.assertRedirects(other.get(reverse('security_settings')), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_regeneration_invalidates_old_recovery_codes(self):
        self.enrolled()
        response = self.client.post(reverse('security_settings'), {'password': self.password, 'code': self.codes[0], 'action': 'recovery_codes'})
        self.assertRedirects(response, reverse('mfa_recovery_codes'), fetch_redirect_response=False)
        self.assertFalse(verify_factor(self.user, self.codes[1]))

    def test_deactivate_reactivate_does_not_revive_old_session(self):
        self.enrolled()
        self.user.is_active = False
        self.user.save()
        self.user.is_active = True
        self.user.save()
        self.assertRedirects(self.client.get(reverse('security_settings')), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_support_reset_revokes_sessions_and_clears_enrollment(self):
        self.enrolled()
        call_command('reset_staff_mfa', self.user.username, reason='Synthetic verified support reference', stdout=StringIO())
        self.state.refresh_from_db()
        self.assertFalse(self.state.confirmed)
        self.assertEqual(self.state.secret, '')
        self.assertEqual(self.state.recovery_hashes, [])
        self.assertRedirects(self.client.get(reverse('security_settings')), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_security_response_private_and_local_assets(self):
        response = self.client.get(reverse('mfa_setup'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn("form-action 'self'", response['Content-Security-Policy'])
        self.assertContains(response, 'security-session.js')
        self.assertNotContains(response, 'api.qrserver')

    def test_heartbeat_requires_csrf(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.enrolled(protected)
        self.assertEqual(protected.post(reverse('security_session')).status_code, 403)

    def test_verified_heartbeat_updates_activity(self):
        self.enrolled()
        self.change_session(security_last_activity=time.time() - 30)
        response = self.client.post(reverse('security_session'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['authenticated'])
        self.assertLess(time.time() - self.client.session['security_last_activity'], 2)

    def test_patient_role_does_not_require_mfa(self):
        UserProfile.objects.filter(user=self.user).update(role=UserProfile.Role.CLIENT)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('security_settings')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('mfa_setup')), reverse('security_settings'), fetch_redirect_response=False)

    def test_superuser_without_profile_requires_mfa(self):
        user = get_user_model().objects.create_superuser('synthetic-admin', password=self.password)
        self.client.force_login(user)
        self.assertRedirects(self.client.get('/admin/'), reverse('mfa_setup'), fetch_redirect_response=False)

    def test_rate_limit_shared_and_spoofed_forwarded_prefix_ignored(self):
        for i in range(10):
            response = Client().post(reverse('login'), {'username': 'invalid', 'password': 'invalid'}, HTTP_X_FORWARDED_FOR=f'192.0.2.{i}, 198.51.100.8')
            self.assertNotEqual(response.status_code, 429)
        response = Client().post(reverse('login'), {'username': 'invalid', 'password': 'invalid'}, HTTP_X_FORWARDED_FOR='203.0.113.2, 198.51.100.8')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(RateLimitBucket.objects.count(), 1)

    def test_expired_rate_limit_window_resets(self):
        for _ in range(11):
            response = Client().post(reverse('login'), {'username': 'invalid', 'password': 'invalid'})
        self.assertEqual(response.status_code, 429)
        RateLimitBucket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertNotEqual(Client().post(reverse('login'), {'username': 'invalid', 'password': 'invalid'}).status_code, 429)

    def test_admin_password_login_is_rate_limited(self):
        for _ in range(10):
            self.assertNotEqual(Client().post('/admin/login/', {'username': 'invalid', 'password': 'invalid'}).status_code, 429)
        self.assertEqual(Client().post('/admin/login/', {'username': 'invalid', 'password': 'invalid'}).status_code, 429)

    def test_password_reset_preserves_mfa_and_invalidates_previous_auth(self):
        self.enrolled()
        self.user.set_password('Synthetic-new-password-42!')
        self.user.save()
        self.state.refresh_from_db()
        self.assertTrue(self.state.confirmed)
        self.assertEqual(self.state.secret, self.secret)
        self.assertNotIn('_auth_user_id', self.client.get(reverse('security_settings')).wsgi_request.session)

    def test_factor_snapshot_cannot_authorize_after_concurrent_revocation(self):
        self.enrolled()
        snapshot = verify_factor(self.user, self.codes[0])
        AccountSecurity.objects.filter(pk=self.state.pk).update(session_version=uuid.uuid4())
        self.change_session(security_version=str(snapshot.session_version), mfa_version=str(snapshot.session_version))
        self.assertRedirects(self.client.get(reverse('security_settings')), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_expired_enrollment_cannot_be_submitted(self):
        self.client.get(reverse('mfa_setup'))
        pending = self.client.session['mfa_pending']
        secret = decrypt_session_value(pending['secret'])
        pending['started'] = time.time() - 601
        self.change_session(mfa_pending=pending)
        self.assertEqual(self.client.post(reverse('mfa_setup'), {'password': self.password, 'code': pyotp.TOTP(secret).now()}).status_code, 200)
        self.state.refresh_from_db()
        self.assertFalse(self.state.confirmed)

    def test_staff_temporary_password_page_obeys_pending_deadline(self):
        UserProfile.objects.filter(user=self.user).update(must_change_password=True)
        self.change_session(security_password_at=time.time() - 601)
        self.assertRedirects(self.client.get(reverse('force_password_change')), '/login/?session_expired=1', fetch_redirect_response=False)

    def test_patient_changing_temporary_password_can_keep_session_active(self):
        UserProfile.objects.filter(user=self.user).update(role=UserProfile.Role.CLIENT, must_change_password=True)
        self.assertEqual(self.client.post(reverse('security_session')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('security_settings')), reverse('force_password_change'), fetch_redirect_response=False)


@override_settings(MFA_REQUIRED=True, FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConcurrentFactorTests(ProtectedRecordsTransactionTestCase):
    def test_same_recovery_code_can_succeed_only_once_across_workers(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Production row-lock concurrency requires PostgreSQL.')
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        user = get_user_model().objects.create_user('concurrent-security', password='Synthetic-password-42!')
        state = security_state(user)
        state.confirmed = True
        state.secret = pyotp.random_base32()
        code = new_recovery_codes(state)[0]
        state.save()
        barrier = Barrier(2)

        def attempt():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                return bool(verify_factor(actor, code))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(results), [False, True])
