from django.core.exceptions import ValidationError
from django.db import models


def client_document_upload_path(instance, filename):
    return f"practices/{instance.practice_id}/clients/{instance.client_id}/documents/{filename}"


class ClientDocument(models.Model):
    class DocumentType(models.TextChoices):
        CONSENT = "consent", "Consent Form"
        INTAKE = "intake", "Intake Form"
        INSURANCE = "insurance", "Insurance Document"
        CLINICAL = "clinical", "Clinical Document"
        OTHER = "other", "Other"

    class ExternalStorageProvider(models.TextChoices):
        NONE = "none", "None"
        GOOGLE_DRIVE = "google_drive", "Google Drive"

    class SyncStatus(models.TextChoices):
        NOT_SYNCED = "not_synced", "Not Synced"
        PENDING = "pending", "Pending"
        SYNCED = "synced", "Synced"
        FAILED = "failed", "Failed"
        DISABLED = "disabled", "Disabled"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="documents")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="uploaded_documents")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices, default=DocumentType.OTHER)
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to=client_document_upload_path)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    visible_to_client = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    external_storage_provider = models.CharField(max_length=30, choices=ExternalStorageProvider.choices, default=ExternalStorageProvider.NONE)
    external_file_id = models.CharField(max_length=255, blank=True)
    external_file_url = models.URLField(blank=True)
    external_synced_at = models.DateTimeField(null=True, blank=True)
    external_sync_status = models.CharField(max_length=20, choices=SyncStatus.choices, default=SyncStatus.NOT_SYNCED)
    external_sync_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Document client must belong to the same practice."})

    def __str__(self):
        return self.title
