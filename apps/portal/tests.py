from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.clients.models import Client
from apps.portal.models import ClientPortalAccess
from apps.practices.models import Practice


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
