from django.core.exceptions import ValidationError
from django.db import models


class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        IN_APP = "in_app", "In App"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="notifications")
    recipient_user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Notification client must belong to the same practice."})

    def __str__(self):
        return f"{self.get_channel_display()} notification: {self.subject}"
