from django.core.exceptions import ValidationError
from django.db import models


class Appointment(models.Model):
    """Scheduled session between a client and a therapist."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"

    class AppointmentType(models.TextChoices):
        IN_PERSON = "in_person", "In Person"
        VIDEO = "video", "Video Call"
        PHONE = "phone", "Phone Call"

    class CalendarProvider(models.TextChoices):
        NONE = "none", "None"
        GOOGLE = "google", "Google Calendar"

    class SyncStatus(models.TextChoices):
        NOT_SYNCED = "not_synced", "Not Synced"
        PENDING = "pending", "Pending"
        SYNCED = "synced", "Synced"
        FAILED = "failed", "Failed"
        DISABLED = "disabled", "Disabled"

    class ReminderStatus(models.TextChoices):
        NOT_SCHEDULED = "not_scheduled", "Not Scheduled"
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        DISABLED = "disabled", "Disabled"

    practice = models.ForeignKey(
        "practices.Practice",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    therapist = models.ForeignKey(
        "practices.TherapistProfile",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    appointment_type = models.CharField(
        max_length=20,
        choices=AppointmentType.choices,
        default=AppointmentType.VIDEO,
    )
    location = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    # Future calendar sync metadata. OAuth tokens should live in a separate
    # integration model, never directly on appointments.
    sync_enabled = models.BooleanField(default=False)
    external_calendar_provider = models.CharField(
        max_length=20,
        choices=CalendarProvider.choices,
        default=CalendarProvider.NONE,
    )
    external_calendar_id = models.CharField(max_length=255, blank=True)
    external_event_id = models.CharField(max_length=255, blank=True)
    external_event_url = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.NOT_SYNCED,
    )
    sync_error = models.TextField(blank=True)
    reminder_enabled = models.BooleanField(default=True)
    reminder_status = models.CharField(max_length=20, choices=ReminderStatus.choices, default=ReminderStatus.PENDING)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]

    def clean(self):
        super().clean()
        errors = {}

        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "The appointment must end after it starts."

        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "The client must belong to the same practice as the appointment."

        if self.therapist_id and self.practice_id and self.therapist.practice_id != self.practice_id:
            errors["therapist"] = "The therapist must belong to the same practice as the appointment."

        if not self.sync_enabled and self.sync_status not in {
            self.SyncStatus.NOT_SYNCED,
            self.SyncStatus.DISABLED,
        }:
            errors["sync_status"] = "Disabled calendar sync cannot be marked pending, synced, or failed."

        if not self.reminder_enabled and self.reminder_status not in {
            self.ReminderStatus.NOT_SCHEDULED,
            self.ReminderStatus.DISABLED,
        }:
            errors["reminder_status"] = "Disabled reminders cannot be marked pending, sent, or failed."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.client} with {self.therapist} at {self.starts_at:%Y-%m-%d %H:%M}"
