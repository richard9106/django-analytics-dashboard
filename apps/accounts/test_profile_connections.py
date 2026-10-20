from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.practices.models import Practice, ExternalIntegration
from apps.billing.models import PracticeSubscription
from .models import UserProfile


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ProfileConnectionTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Fictional Profile Practice')
        self.user = get_user_model().objects.create_user('profile-owner', email='owner@example.invalid')
        UserProfile.objects.create(user=self.user, practice=self.practice, role=UserProfile.Role.OWNER)
        self.client.force_login(self.user)

    def connect(self, **kwargs):
        return ExternalIntegration.objects.create(practice=self.practice, provider='google',
            status=ExternalIntegration.Status.CONNECTED, account_email='connected@example.invalid', **kwargs)

    def page(self):
        return self.client.get(reverse('profile_settings'))

    def test_read_only_gmail_is_connected_without_send_permission(self):
        self.connect(read_email_enabled=True)
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['practice_setup_gmail'])
        self.assertTrue(response.context['google_workspace_connected'])
        self.assertContains(response, 'connected@example.invalid')
        self.assertContains(response, '<li>Inbox</li>')
        self.assertNotContains(response, 'Connect Gmail')
        self.assertNotContains(response, '>Connect Google</a>')
        self.assertNotContains(response, 'setup-checklist-panel')

    def test_calendar_connection_is_not_misrepresented_as_missing_google_or_gmail_send(self):
        self.connect(calendar_enabled=True)
        response = self.page()
        self.assertTrue(response.context['google_workspace_connected'])
        self.assertFalse(response.context['practice_setup_gmail'])
        self.assertContains(response, '<li>Calendar</li>')
        self.assertNotContains(response, '>Connect Google</a>')
        self.assertNotContains(response, '<li>Gmail sending</li>')
        self.assertContains(response, 'My Google workspace')

    def test_reauthorization_is_visible_even_with_previous_email_and_selected_capabilities(self):
        integration = self.connect(send_email_enabled=True)
        integration.status = ExternalIntegration.Status.NEEDS_REAUTH
        integration.save()
        response = self.page()
        self.assertFalse(response.context['google_workspace_connected'])
        self.assertContains(response, 'Reconnect needed')
        self.assertContains(response, 'Reconnect Google')
        self.assertNotContains(response, '<li>Gmail sending</li>')

    def test_disconnected_or_other_practice_connection_does_not_appear_connected(self):
        other = Practice.objects.create(name='Other fictional practice')
        ExternalIntegration.objects.create(practice=other, provider='google', status='connected',
            account_email='other@example.invalid', send_email_enabled=True)
        response = self.page()
        self.assertContains(response, 'Not connected')
        self.assertContains(response, '>Connect Google</a>')
        self.assertNotContains(response, 'other@example.invalid')
        own = self.connect(read_email_enabled=True)
        own.disconnect(); own.save()
        self.assertContains(self.page(), 'Not connected')

    def test_complete_optional_connections_remove_shared_reminder(self):
        self.connect(calendar_enabled=True)
        self.practice.stripe_connect_account_id = 'acct_fictional'
        self.practice.stripe_connect_charges_enabled = True
        self.practice.stripe_connect_payouts_enabled = True
        self.practice.save()
        response = self.page()
        self.assertTrue(response.context['practice_setup_complete'])
        self.assertNotContains(response, 'setup-reminder')
        self.assertContains(response, '>Ready</span>')

    def test_invalid_profile_edit_keeps_bound_form_and_opens_modal(self):
        response = self.client.post(reverse('profile_settings'), {
            'first_name': 'Fictional corrected name', 'last_name': 'Owner', 'email': 'invalid', 'phone': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-errors')
        self.assertContains(response, 'Fictional corrected name')
        self.assertIn('email', response.context['profile_form'].errors)

    @patch('apps.accounts.views.ProfileSettingsView.get_subscription_invoices')
    def test_therapists_do_not_fetch_or_receive_practice_billing_actions(self, invoices):
        UserProfile.objects.filter(user=self.user).update(role=UserProfile.Role.THERAPIST)
        PracticeSubscription.objects.create(practice=self.practice, plan='solo', billing_period='monthly',
            status='active', stripe_customer_id='cus_fictional', stripe_subscription_id='sub_fictional')
        response = self.page()
        invoices.assert_not_called()
        self.assertNotContains(response, 'NuviaMy invoices')
        self.assertNotContains(response, 'id="plan-change-modal"')
        self.assertNotContains(response, 'Prepare secure download')
        self.assertContains(response, 'Contact your practice owner to manage billing.')

    def test_export_disclosure_preserves_owner_export_form(self):
        response = self.page()
        self.assertContains(response, 'profile-export-section')
        self.assertContains(response, 'name="scope" value="all" checked')
        self.assertContains(response, reverse('practice_data_export'))
        self.assertContains(response, 'Prepare secure download')
