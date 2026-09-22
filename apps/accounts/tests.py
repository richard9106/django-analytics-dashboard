from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

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
