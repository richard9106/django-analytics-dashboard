from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class SessionNoteQuerySet(models.QuerySet):
    def _protect_locked(self):
        # Lock before checking to prevent concurrent finalization from racing a write.
        if any(self.select_for_update().values_list('is_locked', flat=True)):
            raise ValidationError('Locked clinical notes cannot be changed or deleted.')

    @transaction.atomic
    def update(self, **kwargs):
        self._protect_locked()
        return super().update(**kwargs)

    @transaction.atomic
    def delete(self):
        self._protect_locked()
        return super().delete()


class SessionNote(models.Model):
    """Clinical documentation for a client session or related clinical event."""

    class NoteType(models.TextChoices):
        PROGRESS_NOTE = "progress_note", "Progress Note"
        INTAKE_NOTE = "intake_note", "Intake Note"
        TREATMENT_PLAN = "treatment_plan", "Treatment Plan"
        GENERAL_NOTE = "general_note", "General Note"

    practice = models.ForeignKey(
        "practices.Practice",
        on_delete=models.PROTECT,
        related_name="session_notes",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="session_notes",
    )
    therapist = models.ForeignKey(
        "practices.TherapistProfile",
        on_delete=models.PROTECT,
        related_name="session_notes",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="session_notes",
    )
    treatment_plan = models.ForeignKey(
        "clinical.TreatmentPlan",
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
    treatment_progress = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SessionNoteQuerySet.as_manager()

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

        if self.treatment_plan_id:
            if self.practice_id and self.treatment_plan.practice_id != self.practice_id:
                errors.setdefault("treatment_plan", []).append(
                    "The treatment plan must belong to the same practice as the note."
                )
            if self.client_id and self.treatment_plan.client_id != self.client_id:
                errors.setdefault("treatment_plan", []).append(
                    "The treatment plan client must match the note client."
                )

        if self.locked_at and not self.is_locked:
            errors["locked_at"] = "A note cannot have locked_at set unless it is locked."
        if self.is_locked and not self.locked_at:
            errors["locked_at"] = "A locked note must have locked_at set."

        if errors:
            raise ValidationError(errors)

    @property
    def signed_at(self):
        signature = getattr(self, 'signature', None)
        return signature.signed_at if signature else None

    @property
    def signed_by_id(self):
        signature = getattr(self, 'signature', None)
        return signature.signed_by_id if signature else None

    @property
    def signer_name(self):
        signature = getattr(self, 'signature', None)
        return signature.signer_name if signature else ''

    @property
    def signature_digest(self):
        signature = getattr(self, 'signature', None)
        return signature.digest if signature else ''

    def review_digest(self):
        import hashlib
        import json
        payload = [self.pk, self.practice_id, self.client_id, self.therapist_id,
                   self.appointment_id, self.treatment_plan_id, self.note_type,
                   self.content, self.treatment_progress]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

    @transaction.atomic
    def sign(self, user, reviewed_digest):
        import secrets
        note = type(self).objects.select_for_update(of=('self',)).select_related('therapist__user', 'appointment', 'signature').get(pk=self.pk)
        if note.therapist.user_id != user.pk:
            raise ValidationError('Only the responsible therapist can sign this note.')
        if note.signed_at:
            raise ValidationError('This note has already been signed.')
        if not note.content.strip():
            raise ValidationError('Write the clinical note before signing it.')
        if not secrets.compare_digest(note.review_digest(), reviewed_digest):
            raise ValidationError('The note changed after review. Review the current version before signing.')
        if note.appointment and note.appointment.ends_at > timezone.now():
            raise ValidationError('The session must end before its note is signed.')
        if not note.is_locked:
            note.is_locked = True
            note.locked_at = timezone.now()
            note.full_clean()
            note.save()
        signature = SessionNoteSignature.objects.create(note=note, signed_by=user,
            signer_name=user.get_full_name() or user.get_username(), digest=note.review_digest())
        note.signature = signature
        return note

    def lock(self):
        self.is_locked = True
        self.locked_at = timezone.now()

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Keep finalized notes immutable through all normal model saves."""
        if self.pk:
            previous = type(self).objects.select_for_update().filter(pk=self.pk).values("is_locked").first()
            if previous and previous["is_locked"]:
                raise ValidationError("Locked clinical notes cannot be edited or unlocked.")
        if self.is_locked and not self.locked_at:
            self.locked_at = timezone.now()
        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        current = type(self).objects.select_for_update().filter(pk=self.pk).values_list("is_locked", flat=True).first()
        if current:
            raise ValidationError("Locked clinical notes cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.get_note_type_display()} for {self.client}"


class Diagnosis(models.Model):
    practice = models.ForeignKey("practices.Practice", on_delete=models.PROTECT, related_name="diagnoses")
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="diagnoses")
    code = models.CharField(max_length=20)
    label = models.CharField(max_length=180)
    diagnosed_at = models.DateField(default=timezone.localdate)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-diagnosed_at", "code"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "client", "code"], name="unique_diagnosis_code_per_client"),
        ]

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Diagnosis client must belong to the same practice."})

    def __str__(self):
        return f"{self.code} - {self.client}"


class TreatmentPlan(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVIEW_DUE = "review_due", "Review Due"
        COMPLETED = "completed", "Completed"
        DISCONTINUED = "discontinued", "Discontinued"

    practice = models.ForeignKey("practices.Practice", on_delete=models.PROTECT, related_name="treatment_plans")
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="treatment_plans")
    therapist = models.ForeignKey("practices.TherapistProfile", on_delete=models.PROTECT, related_name="treatment_plans")
    diagnoses = models.ManyToManyField(Diagnosis, blank=True, related_name="treatment_plans")
    title = models.CharField(max_length=160)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    goals = models.TextField()
    objectives = models.TextField(blank=True)
    interventions = models.TextField(blank=True)
    start_date = models.DateField(default=timezone.localdate)
    review_date = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "client__last_name"]

    def clean(self):
        errors = {}
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "Treatment plan client must belong to the same practice."
        if self.therapist_id and self.practice_id and self.therapist.practice_id != self.practice_id:
            errors["therapist"] = "Treatment plan therapist must belong to the same practice."
        if self.review_date and self.start_date and self.review_date < self.start_date:
            errors["review_date"] = "Review date cannot be before the plan start date."
        if self.completed_at and self.start_date and self.completed_at < self.start_date:
            errors["completed_at"] = "Completed date cannot be before the plan start date."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.title} - {self.client}"

    @property
    def is_review_due(self):
        return (
            self.status in {self.Status.ACTIVE, self.Status.REVIEW_DUE}
            and self.review_date is not None
            and self.review_date <= timezone.localdate()
        )


class SignatureQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Signatures are immutable.')

    def delete(self):
        raise ValidationError('Signatures cannot be deleted.')


class SessionNoteSignature(models.Model):
    note = models.OneToOneField(SessionNote, on_delete=models.PROTECT, related_name='signature')
    signed_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='session_note_signatures')
    signed_at = models.DateTimeField(default=timezone.now)
    signer_name = models.CharField(max_length=320)
    digest = models.CharField(max_length=64)
    objects = SignatureQuerySet.as_manager()

    def clean(self):
        if not self.note.content.strip():
            raise ValidationError('A signature requires clinical note content.')
        if not self.note.is_locked or self.note.therapist.user_id != self.signed_by_id:
            raise ValidationError('The responsible therapist must attest to a finalized note.')
        if self.digest != self.note.review_digest():
            raise ValidationError('Signature content does not match the reviewed note.')

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Signatures are immutable.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Signatures cannot be deleted.')
