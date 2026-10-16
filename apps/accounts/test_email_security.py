import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AccountSecurity


@override_settings(EMAIL_TWO_STEP_REQUIRED=True, MFA_REQUIRED=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EmailSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('email-step', 'richard@example.com', 'password123!')
        self.client.force_login(self.user)
        self.url = reverse('email_security_challenge')

    def code(self):
        return re.search(r'code is ([0-9]{6})', mail.outbox[-1].body)[1]

    def test_pending_session_cannot_read_dashboard_admin_or_export(self):
        for path in ['/dashboard/', '/admin/', '/accounts/export/']:
            self.assertRedirects(self.client.get(path), self.url, fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('security_session')).status_code, 401)

    def test_verification_and_single_use(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'r••••@example.com')
        code = self.code()
        state = AccountSecurity.objects.get(user=self.user)
        self.assertNotEqual(state.email_code_hash, code)
        self.client.post(self.url, {'code': code})
        self.assertIn('email_verified_binding', self.client.session)
        state.refresh_from_db()
        self.assertEqual(state.email_code_hash, '')
        self.client.force_login(self.user)
        self.client.get(self.url)
        self.client.post(self.url, {'code': code})
        self.assertNotIn('email_verified_binding', self.client.session)

    def test_expiration(self):
        self.client.get(self.url)
        AccountSecurity.objects.filter(user=self.user).update(email_code_sent_at=timezone.now()-timedelta(minutes=11))
        self.assertContains(self.client.post(self.url, {'code': self.code()}), 'incorrect or expired')

    def test_lockout_persists_across_sessions_and_resend(self):
        self.client.get(self.url)
        for _ in range(5):
            self.client.post(self.url, {'code': '999999' if self.code() != '999999' else '000000'})
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url), 'Too many attempts')
        self.client.post(self.url, {'action': 'resend'})
        self.assertEqual(len(mail.outbox), 1)

    def test_cooldown_and_new_code_invalidates_old(self):
        self.client.get(self.url)
        old = self.code()
        self.client.post(self.url, {'action': 'resend'})
        self.assertEqual(len(mail.outbox), 1)
        AccountSecurity.objects.filter(user=self.user).update(email_code_sent_at=timezone.now()-timedelta(seconds=61))
        self.client.post(self.url, {'action': 'resend'})
        self.assertEqual(len(mail.outbox), 2)
        if old != self.code():
            self.assertContains(self.client.post(self.url, {'code': old}), 'incorrect or expired')

    def test_other_session_cannot_reuse_code(self):
        self.client.get(self.url)
        other = Client()
        other.force_login(self.user)
        other.get(self.url)
        other.post(self.url, {'code': self.code()})
        self.assertNotIn('email_verified_binding', other.session)

    def test_email_change_requires_verification_again(self):
        self.client.get(self.url)
        self.client.post(self.url, {'code': self.code()})
        self.user.email = 'new@example.com'
        self.user.save(update_fields=['email'])
        self.assertRedirects(self.client.get('/dashboard/'), self.url, fetch_redirect_response=False)

    @patch('apps.accounts.email_security.send_mail', side_effect=RuntimeError('smtp failed'))
    def test_delivery_failure_fails_closed(self, send):
        self.assertContains(self.client.get(self.url), 'could not send')
        self.assertEqual(AccountSecurity.objects.get(user=self.user).email_code_hash, '')
        self.assertNotIn('email_verified_binding', self.client.session)

    def test_logout_allowed_and_csrf_required(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(self.url, {'code': '123456'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)

    def test_headers(self):
        response = self.client.get(self.url)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])

    def test_password_login_goes_directly_to_email_step(self):
        self.client.logout()
        response = self.client.post(reverse('login'), {'username': self.user.email, 'password': 'password123!'})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/dashboard/'), self.url, fetch_redirect_response=False)

    def test_expired_subscription_does_not_block_code_submission(self):
        from apps.practices.models import Practice
        from .models import UserProfile
        practice = Practice.objects.create(name='Email verification fixture', subscription_required=True,
                                          free_trial_ends_at=timezone.now()-timedelta(days=1))
        UserProfile.objects.create(user=self.user, practice=practice, role=UserProfile.Role.OWNER)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, {'code': self.code()})
        self.assertIn('email_verified_binding', self.client.session)

    def test_missing_email_fails_closed(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])
        self.assertContains(self.client.get(self.url), 'could not send')
        self.assertFalse(mail.outbox)
