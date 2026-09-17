import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Client(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archive"

    practice = models.ForeignKey(
        "practices.Practice",
        on_delete=models.CASCADE,
        related_name="clients",
    )
    primary_therapist = models.ForeignKey(
        "practices.TherapistProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="primary_clients",
    )
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    insurance_provider = models.CharField(max_length=140, blank=True)
    insurance_member_id = models.CharField(max_length=80, blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=140, blank=True)
    address_line2 = models.CharField(max_length=140, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Client"

    def clean(self):
        if (
            self.primary_therapist
            and self.practice
            and self.primary_therapist.practice != self.practice
        ):
            raise ValidationError(
                "Primary therapist must belong to the same practice as the client."
            )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
