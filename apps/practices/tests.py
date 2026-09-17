from django.contrib.auth import get_user_model
from django.test import TestCase
from django.db import IntegrityError

from .models import Practice, TherapistProfile


class PracticeModelTests(TestCase):
    
    def test_practice_string_uses_name_and_types(self):
        practice = Practice.objects.create(
            name="Nuvia Wellnes",
            practice_type=Practice.PracticeType.CLINIC,
        )
        
        self.assertEqual(str(practice), "Nuvia Wellnes - Clinic / Group Practice")

    def test_therapist_profile_string_use_rigth_strings(self):
        user = get_user_model().objects.create_user(
            username="drsmith",
            first_name="Jane",
            last_name="Smith",
        )
        practice = Practice.objects.create(name="Nuvia Wellnes")
        profile = TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number="ADBd",
            license_state="CA"
        )
        
        self.assertEqual(str(profile), "Jane Smith - Nuvia Wellnes")
        
    def test_license_number_unique_per_state(self):
        practice = Practice.objects.create(name="Nuvia Wellnes")
        firts_user = get_user_model().objects.create_user(username="Julia")
        second_user = get_user_model().objects.create_user(username="Maria")
        
        TherapistProfile.objects.create(
            user=firts_user,
            practice=practice,
            license_number="ABC123",
            license_state="CA",
        )
        
        with self.assertRaises(IntegrityError):
            TherapistProfile.objects.create(
                user=second_user,
                practice=practice,
                license_number="ABC123",
                license_state="CA",
            )
            
    def test_licens_can_repeat_in_diferent_states(self):
        practice = Practice.objects.create(name="Nuvia Wellnes")
        firts_user = get_user_model().objects.create_user(username="Julia")
        second_user = get_user_model().objects.create_user(username="Maria")
        
        TherapistProfile.objects.create(
            user=firts_user,
            practice=practice,
            license_number="ABC123",
            license_state="CA",
        )
        
        second_profile = TherapistProfile.objects.create(
            user=second_user,
            practice=practice,
            license_number="ABC123",
            license_state="NY",
        )
        
        self.assertEqual(second_profile.license_state, "NY")