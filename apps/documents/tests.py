from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
import tempfile

from apps.accounts.models import UserProfile
from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.portal.models import ClientPortalAccess
from apps.practices.models import Practice, TherapistProfile


class ClientDocumentModelTests(TestCase):
    def test_document_rejects_client_from_other_practice(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        other_practice = Practice.objects.create(name="Other Clinic")
        user = get_user_model().objects.create_user(username="admin")
        client = Client.objects.create(practice=other_practice, first_name="Ana", last_name="Perez")
        document = ClientDocument(
            practice=practice,
            client=client,
            uploaded_by=user,
            title="Insurance Card",
            file=SimpleUploadedFile("insurance.txt", b"demo"),
        )

        with self.assertRaisesMessage(ValidationError, "same practice"):
            document.full_clean()

    def test_document_upload_path_is_practice_scoped(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        client = Client.objects.create(practice=practice, first_name="Ana", last_name="Perez")
        document = ClientDocument(
            practice=practice,
            client=client,
            title="Consent",
            file=SimpleUploadedFile("consent.txt", b"demo"),
        )

        document.full_clean()
        self.assertIn(f"practices/{practice.id}/clients/{client.id}/documents/", document.file.field.generate_filename(document, "consent.txt"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ClientDocumentViewTests(TestCase):
    def create_practice_user(self, username="drsmith", practice_name="NuviaMy Wellness"):
        user = get_user_model().objects.create_user(
            username=username,
            password="StrongPass123!",
            first_name="Laura",
            last_name="Smith",
        )
        practice = Practice.objects.create(name=practice_name)
        therapist = TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number=f"{username}-12345",
            license_state="CA",
        )
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        return user, practice, therapist, client

    def test_document_list_requires_login(self):
        response = self.client.get(reverse("documents:list"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('documents:list')}")

    def test_document_list_is_scoped_to_user_practice(self):
        user, practice, _therapist, client = self.create_practice_user()
        _other_user, other_practice, _other_therapist, other_client = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        ClientDocument.objects.create(
            practice=practice,
            client=client,
            uploaded_by=user,
            title="Visible consent",
            file=SimpleUploadedFile("visible.txt", b"visible", content_type="text/plain"),
        )
        ClientDocument.objects.create(
            practice=other_practice,
            client=other_client,
            title="Hidden consent",
            file=SimpleUploadedFile("hidden.txt", b"hidden", content_type="text/plain"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("documents:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible consent")
        self.assertContains(response, 'id="document-create-modal"')
        self.assertNotContains(response, "Hidden consent")

    def test_document_upload_saves_metadata(self):
        user, practice, _therapist, client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("documents:create"), {
            "client": client.pk,
            "document_type": ClientDocument.DocumentType.CONSENT,
            "title": "Consent form",
            "file": SimpleUploadedFile("consent.txt", b"signed", content_type="text/plain"),
            "visible_to_client": "on",
            "description": "Signed consent.",
        })

        self.assertRedirects(response, reverse("documents:list"))
        document = ClientDocument.objects.get()
        self.assertEqual(document.practice, practice)
        self.assertEqual(document.uploaded_by, user)
        self.assertEqual(document.original_filename, "consent.txt")
        self.assertEqual(document.content_type, "text/plain")
        self.assertEqual(document.file_size, 6)
        self.assertTrue(document.visible_to_client)

    def test_document_download_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, _other_therapist, other_client = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        document = ClientDocument.objects.create(
            practice=other_practice,
            client=other_client,
            title="Hidden consent",
            file=SimpleUploadedFile("hidden.txt", b"hidden", content_type="text/plain"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("documents:download", args=[document.pk]))

        self.assertEqual(response.status_code, 404)

    def test_document_download_returns_file(self):
        user, practice, _therapist, client = self.create_practice_user()
        document = ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Consent",
            original_filename="consent.txt",
            content_type="text/plain",
            file=SimpleUploadedFile("consent.txt", b"signed", content_type="text/plain"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("documents:download", args=[document.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_portal_client_can_download_visible_document(self):
        _user, practice, _therapist, client = self.create_practice_user()
        portal_user = get_user_model().objects.create_user(username="portal", password="StrongPass123!")
        ClientPortalAccess.objects.create(user=portal_user, practice=practice, client=client, is_active=True)
        document = ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Visible consent",
            original_filename="consent.txt",
            content_type="text/plain",
            visible_to_client=True,
            file=SimpleUploadedFile("consent.txt", b"signed", content_type="text/plain"),
        )

        self.client.force_login(portal_user)
        response = self.client.get(reverse("documents:download", args=[document.pk]))

        self.assertEqual(response.status_code, 200)

    def test_portal_client_cannot_download_hidden_document(self):
        _user, practice, _therapist, client = self.create_practice_user()
        portal_user = get_user_model().objects.create_user(username="portal", password="StrongPass123!")
        ClientPortalAccess.objects.create(user=portal_user, practice=practice, client=client, is_active=True)
        document = ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Internal consent",
            visible_to_client=False,
            file=SimpleUploadedFile("internal.txt", b"hidden", content_type="text/plain"),
        )

        self.client.force_login(portal_user)
        response = self.client.get(reverse("documents:download", args=[document.pk]))

        self.assertEqual(response.status_code, 404)
