from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.portal.models import ClientPortalAccess
from apps.practices.models import ExternalIntegration, Practice, TherapistProfile


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
        self.assertContains(response, "Export to Google Drive")
        self.assertContains(response, "Google Drive: Not Synced")
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

    def test_google_drive_export_uploads_document_and_saves_metadata(self):
        user, practice, _therapist, client = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            file_storage_enabled=True,
            default_folder="NuviaMy Documents",
            access_token="access-token",
            refresh_token="refresh-token",
        )
        document = ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Consent",
            original_filename="consent.txt",
            content_type="text/plain",
            file=SimpleUploadedFile("consent.txt", b"signed", content_type="text/plain"),
        )

        self.client.force_login(user)
        with patch("apps.documents.google_drive.google_api_request") as google_request, patch("apps.documents.google_drive.drive_request") as drive_request:
            google_request.side_effect = [
                {"files": []},
                {"id": "drive-folder-123"},
            ]
            drive_request.return_value = {"id": "drive-file-123", "webViewLink": "https://drive.google.com/file/123"}
            response = self.client.post(reverse("documents:google_drive_export", args=[document.pk]))

        self.assertRedirects(response, reverse("documents:list"))
        document.refresh_from_db()
        self.assertEqual(document.external_storage_provider, ClientDocument.ExternalStorageProvider.GOOGLE_DRIVE)
        self.assertEqual(document.external_sync_status, ClientDocument.SyncStatus.SYNCED)
        self.assertEqual(document.external_file_id, "drive-file-123")
        self.assertEqual(document.external_file_url, "https://drive.google.com/file/123")
        self.assertEqual(drive_request.call_args.kwargs["method"], "POST")
        log = AuditLog.objects.get(action=AuditLog.Action.EXPORT, object_type="documents.ClientDocument")
        self.assertEqual(log.metadata["provider"], "google_drive")
        self.assertEqual(log.metadata["status"], ClientDocument.SyncStatus.SYNCED)

    def test_google_drive_export_is_scoped_to_user_practice(self):
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
        response = self.client.post(reverse("documents:google_drive_export", args=[document.pk]))

        self.assertEqual(response.status_code, 404)

    def test_google_drive_export_restores_file_deleted_from_drive(self):
        user, practice, _therapist, client = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            file_storage_enabled=True,
            access_token="access-token",
            refresh_token="refresh-token",
        )
        document = ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Consent",
            original_filename="consent.txt",
            content_type="text/plain",
            external_storage_provider=ClientDocument.ExternalStorageProvider.GOOGLE_DRIVE,
            external_file_id="deleted-drive-file",
            external_sync_status=ClientDocument.SyncStatus.SYNCED,
            file=SimpleUploadedFile("consent.txt", b"signed", content_type="text/plain"),
        )

        self.client.force_login(user)
        with patch("apps.documents.google_drive.drive_request") as drive_request:
            drive_request.side_effect = [
                HTTPError("https://drive.example/files/deleted-drive-file", 404, "Not Found", None, None),
                {"id": "replacement-drive-file", "webViewLink": "https://drive.google.com/file/replacement"},
            ]
            response = self.client.post(reverse("documents:google_drive_export", args=[document.pk]))

        self.assertRedirects(response, reverse("documents:list"))
        document.refresh_from_db()
        self.assertEqual(document.external_file_id, "replacement-drive-file")
        self.assertEqual(document.external_sync_status, ClientDocument.SyncStatus.SYNCED)
        self.assertEqual(drive_request.call_args_list[0].kwargs["method"], "PATCH")
        self.assertEqual(drive_request.call_args_list[1].kwargs["method"], "POST")
