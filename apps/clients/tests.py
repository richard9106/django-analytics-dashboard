from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model


from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile


class ClientModelTests(TestCase):
    
    def setUp(self):
        self.practice = Practice.objects.create(name="Nuvia Wellnes")
        self.user = get_user_model().objects.create_user(username="drSmith")
        self.therapist = TherapistProfile.objects.create(
            user=self.user,
            practice=self.practice,
            license_number="ABC123",
            license_state="CA",
        )
        
    def test_client_string_retun_full_name(self):
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice
        )
        
        self.assertEqual(str(client), "Ana Perez")
        
    def test_public_id_is_created(self):
        """test public id"""
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice,
            primary_therapist=self.therapist,
        )
        
        self.assertIsNotNone(client.public_id)
        
    def test_client_can_have_primary_therapist_from_same_practice(self):
        """can have a client can have therapist from same practice"""
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice,
            primary_therapist=self.therapist,
        )
        
        client.full_clean()

    def test_client_can_exit_without_primary_therapist(self):
        """can have a client can have therapist from same practice"""
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice,
        )
        
        client.full_clean()
        
    def test_client_rejects_therapist_from_other_practice(self):
        """verify that the client cannot be assigned 
        a primary therapist from a diferent practice"""
        
        other_practice = Practice.objects.create(name="Other clinic")
        other_user = get_user_model().objects.create_user(
            username="othertherapis"
            )
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="ABC123",
            license_state="NY",
        )
        
        client = Client.objects.create(
            primary_therapist=other_therapist,
            practice=self.practice,
            first_name="Ana",
            last_name="Perez",
        )
        
        with self.assertRaises(ValidationError):
            client.full_clean()
