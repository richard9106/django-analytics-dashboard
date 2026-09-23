from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.practices.models import ExternalIntegration, Practice, TherapistProfile


class IntegrationSettingsTests(TestCase):
    def create_practice_user(self):
        user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        practice = Practice.objects.create(name="NuviaMy Wellness")
        TherapistProfile.objects.create(user=user, practice=practice, license_number="LIC-123", license_state="CA")
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.OWNER)
        return user, practice

    def test_integrations_requires_login(self):
        response = self.client.get(reverse("practice_settings:integrations"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('practice_settings:integrations')}")

    def test_integrations_page_shows_supported_providers(self):
        user, _practice = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.get(reverse("practice_settings:integrations"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gmail")
        self.assertContains(response, "Google Drive")
        self.assertContains(response, "Dropbox")

    def test_gmail_integration_settings_save_to_practice(self):
        user, practice = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.post(reverse("practice_settings:integration_update", args=[ExternalIntegration.Provider.GMAIL]), {
            "gmail-account_email": "clinic@example.com",
            "gmail-send_email_enabled": "on",
            "gmail-read_email_enabled": "on",
            "gmail-default_folder": "NuviaMy",
            "gmail-notes": "Use for portal messages.",
        })

        self.assertRedirects(response, reverse("practice_settings:integrations"))
        integration = ExternalIntegration.objects.get()
        self.assertEqual(integration.practice, practice)
        self.assertEqual(integration.provider, ExternalIntegration.Provider.GMAIL)
        self.assertTrue(integration.send_email_enabled)
        self.assertTrue(integration.read_email_enabled)
        self.assertFalse(integration.file_storage_enabled)

    def test_drive_integration_cannot_enable_email_flags(self):
        user, _practice = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.post(reverse("practice_settings:integration_update", args=[ExternalIntegration.Provider.GOOGLE_DRIVE]), {
            "google_drive-account_email": "clinic@example.com",
            "google_drive-send_email_enabled": "on",
            "google_drive-read_email_enabled": "on",
            "google_drive-file_storage_enabled": "on",
            "google_drive-default_folder": "NuviaMy Documents",
            "google_drive-notes": "Store selected files.",
        })

        self.assertRedirects(response, reverse("practice_settings:integrations"))
        integration = ExternalIntegration.objects.get()
        self.assertFalse(integration.send_email_enabled)
        self.assertFalse(integration.read_email_enabled)
        self.assertTrue(integration.file_storage_enabled)
