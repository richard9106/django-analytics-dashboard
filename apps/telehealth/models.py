from django.core.exceptions import ValidationError
from django.db import models


class TelehealthRoom(models.Model):
    class Provider(models.TextChoices):
        MANUAL = "manual", "Manual Link"
        ZOOM = "zoom", "Zoom"
        DAILY = "daily", "Daily"
        TWILIO = "twilio", "Twilio"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="telehealth_rooms")
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.CASCADE, related_name="telehealth_room")
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.MANUAL)
    join_url = models.URLField()
    host_url = models.URLField(blank=True)
    external_room_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.appointment_id and self.practice_id and self.appointment.practice_id != self.practice_id:
            raise ValidationError({"appointment": "Telehealth appointment must belong to the same practice."})
        if self.appointment_id and self.appointment.appointment_type != self.appointment.AppointmentType.VIDEO:
            raise ValidationError({"appointment": "Telehealth rooms can only be attached to video appointments."})

    def __str__(self):
        return f"{self.get_provider_display()} room for {self.appointment}"
