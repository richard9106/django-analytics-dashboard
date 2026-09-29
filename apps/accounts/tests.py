from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.billing.models import PracticeSubscription
from apps.practices.models import Practice, TherapistProfile


class UserProfileModelTests(TestCase):
    def test_therapist_profile_must_match_same_practice(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        other_practice = Practice.objects.create(name="Other Clinic")
        user = get_user_model().objects.create_user(username="drsmith")
        TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number="ABC123",
            license_state="CA",
        )
        profile = UserProfile(user=user, practice=other_practice, role=UserProfile.Role.THERAPIST)

        with self.assertRaisesMessage(ValidationError, "same practice"):
            profile.full_clean()

    def test_admin_role_can_be_assigned_to_practice(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        user = get_user_model().objects.create_user(username="practiceadmin")
        profile = UserProfile(user=user, practice=practice, role=UserProfile.Role.ADMIN)

        profile.full_clean()
        self.assertEqual(str(profile), "practiceadmin - Practice Admin")

    def test_internal_user_profile_respects_subscription_plan_limit(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        owner = get_user_model().objects.create_user(username="owner")
        owner_profile = UserProfile.objects.create(user=owner, practice=practice, role=UserProfile.Role.OWNER)
        subscription = PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.SOLO,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.ACTIVE,
        )
        admin = get_user_model().objects.create_user(username="admin")
        admin_profile = UserProfile(user=admin, practice=practice, role=UserProfile.Role.ADMIN)

        owner_profile.full_clean()
        self.assertEqual(subscription.internal_user_count, 1)
        self.assertEqual(subscription.internal_user_slots_remaining, 0)
        with self.assertRaisesMessage(ValidationError, "allows up to 1 internal user"):
            admin_profile.full_clean()

    def test_client_profile_does_not_count_against_subscription_plan_limit(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        owner = get_user_model().objects.create_user(username="owner")
        UserProfile.objects.create(user=owner, practice=practice, role=UserProfile.Role.OWNER)
        subscription = PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.SOLO,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.ACTIVE,
        )
        client_user = get_user_model().objects.create_user(username="client")
        client_profile = UserProfile(user=client_user, practice=practice, role=UserProfile.Role.CLIENT)

        client_profile.full_clean()
        self.assertEqual(subscription.internal_user_count, 1)


class PracticeSignupViewTests(TestCase):
    def valid_payload(self, **overrides):
        data = {
            "practice_name": "NuviaMy Wellness",
            "practice_type": Practice.PracticeType.SOLO,
            "practice_email": "hello@nuviamy.test",
            "practice_phone": "555-0100",
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "drsmith@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
            "license_number": "ABC123",
            "license_state": "CA",
            "specialty": "Trauma-informed care",
        }
        data.update(overrides)
        return data

    def test_signup_page_loads(self):
        response = self.client.get(reverse("signup"), {"plan": "group", "period": "yearly"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your therapy practice account")
        self.assertContains(response, "Selected plan: Group Practice · Yearly")
        self.assertContains(response, "15-day free trial")
        self.assertContains(response, "Back to home")
        self.assertNotContains(response, "Username")

    def test_signup_creates_practice_user_therapist_and_owner_profile(self):
        response = self.client.post(reverse("signup"), data=self.valid_payload(plan="group", period="yearly"))

        self.assertRedirects(response, reverse("billing:subscribe", args=["group", "yearly"]), fetch_redirect_response=False)
        user = get_user_model().objects.get(email="drsmith@example.com")
        practice = Practice.objects.get(name="NuviaMy Wellness")
        therapist = TherapistProfile.objects.get(user=user)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(therapist.practice, practice)
        self.assertEqual(profile.practice, practice)
        self.assertEqual(profile.role, UserProfile.Role.OWNER)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_signup_rejects_duplicate_email(self):
        get_user_model().objects.create_user(username="drsmith", email="drsmith@example.com")

        response = self.client.post(reverse("signup"), data=self.valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with this email already exists")

    def test_signup_generates_unique_internal_username_from_email(self):
        get_user_model().objects.create_user(username="drsmith")

        response = self.client.post(reverse("signup"), data=self.valid_payload())

        self.assertRedirects(response, reverse("billing:subscribe", args=["solo", "monthly"]), fetch_redirect_response=False)
        user = get_user_model().objects.get(email="drsmith@example.com")
        self.assertEqual(user.username, "drsmith-2")

    def test_signup_rejects_license_duplicate_in_same_state(self):
        practice = Practice.objects.create(name="Existing Practice")
        user = get_user_model().objects.create_user(username="existing")
        TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number="ABC123",
            license_state="CA",
        )

        response = self.client.post(reverse("signup"), data=self.valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A therapist profile with this license already exists")


class ProfileSettingsViewTests(TestCase):
    def create_practice_user(self):
        user = get_user_model().objects.create_user(
            username="drsmith",
            email="drsmith@example.com",
            password="StrongPass123!",
            first_name="Jane",
            last_name="Smith",
        )
        practice = Practice.objects.create(name="NuviaMy Wellness")
        TherapistProfile.objects.create(user=user, practice=practice, license_number="ABC123", license_state="CA")
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.OWNER)
        return user, practice

    def test_profile_settings_requires_login(self):
        response = self.client.get(reverse("profile_settings"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('profile_settings')}")

    def test_profile_settings_shows_subscription(self):
        user, practice = self.create_practice_user()
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.GROUP,
            billing_period=PracticeSubscription.BillingPeriod.YEARLY,
            status="trialing",
            stripe_customer_id="cus_test",
            stripe_subscription_id="sub_test",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("profile_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile & subscription")
        self.assertContains(response, "Group Practice")
        self.assertContains(response, "Yearly billing")
        self.assertContains(response, "1 of 5 internal users used")
        self.assertContains(response, "4 team seats remaining")
        self.assertContains(response, "Change plan")
        self.assertContains(response, "Change subscription plan")
        self.assertContains(response, 'id="plan-change-modal"')
        self.assertContains(response, 'data-plan-change-form')
        self.assertContains(response, "Monthly")
        self.assertContains(response, "Annual")
        self.assertContains(response, reverse("billing:change_plan", args=["clinic", "yearly"]))
        self.assertNotContains(response, "cus_test")
        self.assertNotContains(response, "sub_test")
        self.assertContains(response, reverse("billing:customer_portal"))
        self.assertContains(response, "Manage billing in Stripe")

    def test_dashboard_profile_menu_links_to_profile_settings(self):
        user, _practice = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("profile_settings"))
        self.assertContains(response, 'class="mobile-account-menu"')

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    @patch("apps.accounts.views.stripe.Invoice.list")
    def test_profile_settings_shows_stripe_subscription_invoices(self, mock_invoice_list):
        user, practice = self.create_practice_user()
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.GROUP,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status="active",
            stripe_customer_id="cus_test",
            stripe_subscription_id="sub_test",
        )
        mock_invoice_list.return_value = {
            "data": [{
                "id": "in_123",
                "number": "NUVIA-001",
                "status": "paid",
                "currency": "usd",
                "amount_paid": 7900,
                "created": 1704067200,
                "hosted_invoice_url": "https://invoice.stripe.test/view",
                "invoice_pdf": "https://invoice.stripe.test/pdf",
            }]
        }

        self.client.force_login(user)
        response = self.client.get(reverse("profile_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My NuviaMy invoices")
        self.assertContains(response, "NUVIA-001")
        self.assertContains(response, "USD 79.00")
        self.assertContains(response, "https://invoice.stripe.test/view")
        self.assertContains(response, "https://invoice.stripe.test/pdf")
        mock_invoice_list.assert_called_once_with(customer="cus_test", limit=10)
