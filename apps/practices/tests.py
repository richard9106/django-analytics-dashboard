from django.contrib.auth import get_user_model
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.db import connection
from django.test import TestCase, override_settings
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
        self.assertContains(response, "Connect Google")
        self.assertContains(response, "Gmail: send email")
        self.assertContains(response, "Google Calendar sync")
        self.assertContains(response, "Dropbox")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="client-id", GOOGLE_OAUTH_CLIENT_SECRET="client-secret", GOOGLE_OAUTH_REDIRECT_URI="https://example.com/settings/integrations/google/callback/")
    def test_google_connect_builds_oauth_url_with_selected_scopes(self):
        user, practice = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.post(reverse("practice_settings:google_connect"), {
            "send_email_enabled": "on",
            "calendar_enabled": "on",
            "default_folder": "NuviaMy",
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.url)
        self.assertIn("gmail.send", response.url)
        self.assertIn("calendar.events", response.url)
        integration = ExternalIntegration.objects.get()
        self.assertEqual(integration.practice, practice)
        self.assertEqual(integration.provider, ExternalIntegration.Provider.GOOGLE)
        self.assertTrue(integration.send_email_enabled)
        self.assertTrue(integration.calendar_enabled)
        self.assertIn("https://www.googleapis.com/auth/gmail.send", integration.enabled_scopes)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="client-id", GOOGLE_OAUTH_CLIENT_SECRET="client-secret", GOOGLE_OAUTH_REDIRECT_URI="https://example.com/settings/integrations/google/callback/")
    def test_google_callback_stores_tokens_and_account_email(self):
        user, practice = self.create_practice_user()
        self.client.force_login(user)
        integration = ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            oauth_state="state-123",
            enabled_scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        session = self.client.session
        session["google_oauth_state"] = "state-123"
        session["google_oauth_integration_id"] = integration.pk
        session.save()

        with patch("apps.practices.views.exchange_google_code") as exchange, patch("apps.practices.views.fetch_google_account_email") as fetch_email:
            exchange.return_value = {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
                "scope": "openid email https://www.googleapis.com/auth/gmail.send",
            }
            fetch_email.return_value = "clinic@example.com"
            response = self.client.get(reverse("practice_settings:google_callback"), {"state": "state-123", "code": "code-123"})

        self.assertRedirects(response, reverse("practice_settings:integrations"))
        integration.refresh_from_db()
        self.assertEqual(integration.status, ExternalIntegration.Status.CONNECTED)
        self.assertEqual(integration.account_email, "clinic@example.com")
        self.assertEqual(integration.access_token, "access-token")
        self.assertEqual(integration.refresh_token, "refresh-token")

    def test_google_callback_rejects_state_mismatch(self):
        user, practice = self.create_practice_user()
        self.client.force_login(user)
        integration = ExternalIntegration.objects.create(practice=practice, provider=ExternalIntegration.Provider.GOOGLE, oauth_state="state-123")
        session = self.client.session
        session["google_oauth_state"] = "state-123"
        session["google_oauth_integration_id"] = integration.pk
        session.save()

        response = self.client.get(reverse("practice_settings:google_callback"), {"state": "wrong", "code": "code-123"})

        self.assertEqual(response.status_code, 403)

    def test_google_disconnect_clears_tokens(self):
        user, practice = self.create_practice_user()
        self.client.force_login(user)
        integration = ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            account_email="clinic@example.com",
            access_token="access-token",
            refresh_token="refresh-token",
            send_email_enabled=True,
        )

        response = self.client.post(reverse("practice_settings:google_disconnect"))

        self.assertRedirects(response, reverse("practice_settings:integrations"))
        integration.refresh_from_db()
        self.assertEqual(integration.status, ExternalIntegration.Status.DISCONNECTED)
        self.assertEqual(integration.access_token, "")
        self.assertFalse(integration.send_email_enabled)

    def test_client_cannot_connect_google(self):
        user, practice = self.create_practice_user()
        user.nuvia_profile.role = UserProfile.Role.CLIENT
        user.nuvia_profile.save(update_fields=["role"])
        self.client.force_login(user)

        response = self.client.post(reverse("practice_settings:google_connect"), {"send_email_enabled": "on"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal:dashboard"))

    def test_dropbox_integration_settings_save_to_practice(self):
        user, practice = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.post(reverse("practice_settings:dropbox_update"), {
            "file_storage_enabled": "on",
            "default_folder": "NuviaMy Documents",
            "notes": "Store selected files.",
        })

        self.assertRedirects(response, reverse("practice_settings:integrations"))
        integration = ExternalIntegration.objects.get()
        self.assertEqual(integration.practice, practice)
        self.assertEqual(integration.provider, ExternalIntegration.Provider.DROPBOX)
        self.assertFalse(integration.send_email_enabled)
        self.assertFalse(integration.read_email_enabled)
        self.assertTrue(integration.file_storage_enabled)

    def test_google_workspace_shows_mocked_gmail_and_calendar_data(self):
        user, practice = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            account_email="clinic@example.com",
            access_token="access-token",
            read_email_enabled=True,
            calendar_enabled=True,
        )
        self.client.force_login(user)

        with patch("apps.practices.views.list_gmail_messages") as gmail, patch("apps.practices.views.list_calendar_events") as calendar:
            gmail.return_value = [{"subject": "Client email", "from": "client@example.com", "date": "Today", "snippet": "Hello"}]
            calendar.return_value = [{"summary": "Therapy session", "start": "2026-09-24T10:00:00", "end": "2026-09-24T10:50:00"}]
            response = self.client.get(reverse("practice_settings:google_workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client email")
        self.assertContains(response, "Therapy session")

    def test_google_workspace_send_email_uses_connected_account(self):
        user, practice = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            account_email="clinic@example.com",
            access_token="access-token",
            send_email_enabled=True,
        )
        self.client.force_login(user)

        with patch("apps.practices.views.send_gmail_message") as send_email:
            response = self.client.post(reverse("practice_settings:gmail_send"), {
                "to_email": "client@example.com",
                "subject": "Appointment reminder",
                "body": "See you tomorrow.",
            })

        self.assertRedirects(response, reverse("practice_settings:google_workspace"))
        send_email.assert_called_once()
        args = send_email.call_args.args
        self.assertEqual(args[1], "client@example.com")
        self.assertEqual(args[2], "Appointment reminder")

    def test_google_workspace_send_email_requires_send_scope(self):
        user, practice = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            account_email="clinic@example.com",
            access_token="access-token",
            send_email_enabled=False,
        )
        self.client.force_login(user)

        response = self.client.post(reverse("practice_settings:gmail_send"), {
            "to_email": "client@example.com",
            "subject": "Appointment reminder",
            "body": "See you tomorrow.",
        })

        self.assertEqual(response.status_code, 403)

    @override_settings(FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_oauth_tokens_are_encrypted_at_rest(self):
        _user, practice = self.create_practice_user()

        integration = ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            access_token="access-token",
            refresh_token="refresh-token",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token, refresh_token FROM practices_externalintegration WHERE id = %s",
                [integration.pk],
            )
            stored_access_token, stored_refresh_token = cursor.fetchone()

        self.assertNotEqual(stored_access_token, "access-token")
        self.assertNotEqual(stored_refresh_token, "refresh-token")
        self.assertTrue(stored_access_token.startswith("fernet:"))
        integration.refresh_from_db()
        self.assertEqual(integration.access_token, "access-token")
        self.assertEqual(integration.refresh_token, "refresh-token")
