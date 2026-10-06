import re

from cryptography.fernet import Fernet

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.practices.models import Practice


@override_settings(MFA_REQUIRED=False, FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode(), PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PasswordOnlyLoginTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('password-fixture', email='synthetic-password@example.com', password='Synthetic-password-42!')
        self.practice = Practice.objects.create(name='Synthetic password login')
        UserProfile.objects.create(user=self.user, practice=self.practice, role=UserProfile.Role.OWNER)
        self.browser = Client(enforce_csrf_checks=True)

    def token(self, response):
        return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)

    def login(self):
        page = self.browser.get(reverse('login'), secure=True)
        return self.browser.post(reverse('login'), {'username': self.user.email,
            'password': 'Synthetic-password-42!', 'csrfmiddlewaretoken': self.token(page)},
            secure=True, HTTP_REFERER='https://testserver/login/')

    def test_credentials_reach_dashboard_without_factor_or_second_password(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.assertEqual(self.browser.get(response.url, secure=True).status_code, 200)

    def test_existing_setup_and_challenge_pages_continue_to_dashboard(self):
        self.login()
        for name in ['mfa_setup', 'mfa_challenge']:
            response = self.browser.get(reverse(name), secure=True)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('dashboard'))

    def test_admin_can_sign_in_without_factor(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        self.login()
        self.assertEqual(self.browser.get('/admin/', secure=True).status_code, 200)

    def test_https_logout_with_same_origin_referrer_and_no_origin(self):
        self.login()
        page = self.browser.get(reverse('logout'), secure=True)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page['Referrer-Policy'], 'same-origin')
        self.assertIn('_auth_user_id', self.browser.session)
        response = self.browser.post(reverse('logout'), {'csrfmiddlewaretoken': self.token(page)},
            secure=True, HTTP_REFERER='https://testserver/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.browser.session)

    def test_logout_still_rejects_forged_posts(self):
        self.login()
        self.assertEqual(self.browser.post(reverse('logout'), secure=True).status_code, 403)
        page = self.browser.get(reverse('logout'), secure=True)
        self.assertEqual(self.browser.post(reverse('logout'), {'csrfmiddlewaretoken': self.token(page)},
            secure=True, HTTP_REFERER='https://foreign.example/logout/').status_code, 403)
        self.assertIn('_auth_user_id', self.browser.session)

    @override_settings(MFA_REQUIRED=True)
    def test_logout_also_works_while_mfa_is_pending(self):
        response = self.login()
        self.assertEqual(response.url, reverse('mfa_setup'))
        page = self.browser.get(reverse('mfa_setup'), secure=True)
        self.assertEqual(page['Referrer-Policy'], 'same-origin')
        response = self.browser.post(reverse('logout'), {'csrfmiddlewaretoken': self.token(page)},
            secure=True, HTTP_REFERER='https://testserver' + reverse('mfa_setup'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.browser.session)
