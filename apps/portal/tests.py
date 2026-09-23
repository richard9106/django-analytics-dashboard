from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.appointments.models import Appointment
from apps.billing.models import Invoice, ServicePackage
from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.portal.models import ClientPortalAccess
from apps.practices.models import Practice, TherapistProfile


class ClientPortalAccessModelTests(TestCase):
    def test_portal_access_rejects_client_from_other_practice(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        other_practice = Practice.objects.create(name="Other Clinic")
        user = get_user_model().objects.create_user(username="clientuser")
        client = Client.objects.create(practice=other_practice, first_name="Ana", last_name="Perez")
        access = ClientPortalAccess(user=user, practice=practice, client=client)

        with self.assertRaisesMessage(ValidationError, "same practice"):
            access.full_clean()

    def test_portal_access_defaults_active(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        user = get_user_model().objects.create_user(username="clientuser")
        client = Client.objects.create(practice=practice, first_name="Ana", last_name="Perez")
        access = ClientPortalAccess(user=user, practice=practice, client=client)

        access.full_clean()
        self.assertTrue(access.is_active)


class ClientPortalViewTests(TestCase):
    def create_portal_user(self, username="clientuser", practice_name="NuviaMy Wellness"):
        practice = Practice.objects.create(name=practice_name)
        therapist_user = get_user_model().objects.create_user(username=f"{username}-therapist")
        therapist = TherapistProfile.objects.create(
            user=therapist_user,
            practice=practice,
            license_number=f"{username}-LIC",
            license_state="CA",
        )
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        user = get_user_model().objects.create_user(
            username=username,
            password="StrongPass123!",
            first_name="Maya",
        )
        access = ClientPortalAccess.objects.create(user=user, practice=practice, client=client, is_active=True)
        return user, practice, therapist, client, access

    def test_portal_dashboard_requires_login(self):
        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('portal:dashboard')}")

    def test_non_portal_user_is_forbidden(self):
        user = get_user_model().objects.create_user(username="therapist", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_inactive_portal_user_is_forbidden(self):
        user, _practice, _therapist, _client, access = self.create_portal_user()
        access.is_active = False
        access.save()
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_portal_dashboard_is_scoped_to_linked_client(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        other_client = Client.objects.create(practice=practice, first_name="Hidden", last_name="Client")
        starts_at = timezone.now() + timedelta(days=1)
        Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        Appointment.objects.create(
            practice=practice,
            client=other_client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        Invoice.objects.create(practice=practice, client=client, invoice_number="INV-VISIBLE", amount=Decimal("120.00"))
        Invoice.objects.create(practice=practice, client=other_client, invoice_number="INV-HIDDEN", amount=Decimal("120.00"))
        ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="4 session package",
            sessions_purchased=4,
            sessions_used=1,
            total_price=Decimal("520.00"),
            purchased_at=timezone.localdate(),
        )
        ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Visible document",
            file="visible.txt",
            visible_to_client=True,
        )
        ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Internal document",
            file="internal.txt",
            visible_to_client=False,
        )
        ClientDocument.objects.create(
            practice=practice,
            client=other_client,
            title="Hidden document",
            file="hidden.txt",
            visible_to_client=True,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome")
        self.assertContains(response, "INV-VISIBLE")
        self.assertContains(response, "4 session package")
        self.assertContains(response, "3 of 4 sessions remaining")
        self.assertContains(response, "Visible document")
        self.assertNotContains(response, "INV-HIDDEN")
        self.assertNotContains(response, "Hidden Client")
        self.assertNotContains(response, "Internal document")
        self.assertNotContains(response, "Hidden document")

    def test_portal_settings_list_requires_login(self):
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('portal_settings:portal_access')}")

    def test_portal_settings_list_is_scoped_to_practice(self):
        user, practice, _therapist, client, _access = self.create_portal_user(username="practice-client")
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        other_user, _other_practice, _other_therapist, _other_client, _other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, client.first_name)
        self.assertContains(response, user.username)
        self.assertNotContains(response, other_user.username)

    def test_portal_settings_create_access(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_settings:portal_access_create"), {
            "client": client.pk,
            "username": "maya.portal",
            "email": "maya@example.com",
            "password": "StrongPass123!",
            "is_active": "on",
        })

        self.assertRedirects(response, reverse("portal_settings:portal_access"))
        access = ClientPortalAccess.objects.get()
        self.assertEqual(access.client, client)
        self.assertTrue(access.is_active)
        self.assertTrue(access.user.check_password("StrongPass123!"))

    def test_portal_settings_suggests_client_email_unique_username_and_password(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        get_user_model().objects.create_user(username="maya.johnson")
        Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson", email="maya@example.com")

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-email="maya@example.com"')
        self.assertContains(response, 'data-username="maya.johnson.2"')
        self.assertContains(response, 'data-password="Nuvia-')

    def test_portal_settings_rejects_duplicate_username_case_insensitive(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        get_user_model().objects.create_user(username="Maya.Portal")

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_settings:portal_access_create"), {
            "client": client.pk,
            "username": "maya.portal",
            "email": "maya@example.com",
            "password": "StrongPass123!",
            "is_active": "on",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with this username already exists.")
        self.assertFalse(ClientPortalAccess.objects.exists())

    def test_portal_settings_update_is_scoped_to_practice(self):
        _user, _practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        other_user, other_practice, _other_therapist, _other_client, other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(user=practice_user, practice=Practice.objects.get(name="NuviaMy Wellness"), role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access_edit", args=[other_access.pk]))

        self.assertEqual(response.status_code, 404)
