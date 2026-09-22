from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.practices.models import Practice


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
