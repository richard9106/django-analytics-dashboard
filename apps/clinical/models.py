from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SessionNote(models.Model):
    """Clinical documentation for a client session or related clinical event."""

    class NoteType(models.TextChoices):
        PROGRESS_NOTE = "progress_note", "Progress Note"
        INTAKE_NOTE = "intake_note", "Intake Note"
        TREATMENT_PLAN = "treatment_plan", "Treatment Plan"
        GENERAL_NOTE = "general_note", "General Note"

    practice = models.ForeignKey(
        "practices.Practice",
        on_delete=models.CASCADE,
        related_name="session_notes",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="session_notes",
    )
    therapist = models.ForeignKey(
        "practices.TherapistProfile",
        on_delete=models.CASCADE,
        related_name="session_notes",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="session_notes",
    )
    note_type = models.CharField(
        max_length=30,
        choices=NoteType.choices,
        default=NoteType.GENERAL_NOTE,
    )
    content = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        errors = {}

        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "The client must belong to the same practice as the note."

        if self.therapist_id and self.practice_id and self.therapist.practice_id != self.practice_id:
            errors["therapist"] = "The therapist must belong to the same practice as the note."

        if self.appointment_id:
            if self.practice_id and self.appointment.practice_id != self.practice_id:
                errors.setdefault("appointment", []).append(
                    "The appointment must belong to the same practice as the note."
                )
            if self.client_id and self.appointment.client_id != self.client_id:
                errors.setdefault("appointment", []).append(
                    "The appointment client must match the note client."
                )
            if self.therapist_id and self.appointment.therapist_id != self.therapist_id:
                errors.setdefault("appointment", []).append(
                    "The appointment therapist must match the note therapist."
                )

        if self.locked_at and not self.is_locked:
            errors["locked_at"] = "A note cannot have locked_at set unless it is locked."

        if errors:
            raise ValidationError(errors)

    def lock(self):
        self.is_locked = True
        self.locked_at = timezone.now()

    def __str__(self):
        return f"{self.get_note_type_display()} for {self.client}"
