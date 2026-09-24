from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserProfile
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
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your therapy practice account")
        self.assertContains(response, "Back to home")
        self.assertNotContains(response, "Username")

    def test_signup_creates_practice_user_therapist_and_owner_profile(self):
        response = self.client.post(reverse("signup"), data=self.valid_payload())

        self.assertRedirects(response, reverse("dashboard"))
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

        self.assertRedirects(response, reverse("dashboard"))
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
