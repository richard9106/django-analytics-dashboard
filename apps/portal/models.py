import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.appointments.models import Appointment, practice_allows_interval


class ClientPortalAccess(models.Model):
    """Links a Django user to a client record for portal access."""

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="client_portal_access")
    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="portal_accesses")
    client = models.OneToOneField("clients.Client", on_delete=models.CASCADE, related_name="portal_access")
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Portal client must belong to the same practice."})

    def __str__(self):
        return f"Portal access for {self.client}"


class ClientPortalRequest(models.Model):
    class Category(models.TextChoices):
        RESCHEDULE = "reschedule", "I need to reschedule"
        CANCELLATION = "cancellation", "I need to cancel"
        BILLING = "billing", "Billing question"
        DOCUMENT = "document", "Document question"
        GENERAL = "general", "General message"

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="portal_requests")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="portal_requests")
    appointment = models.ForeignKey("appointments.Appointment", on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_requests")
    submitted_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_requests")
    category = models.CharField(max_length=30, choices=Category.choices)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["appointment"],
                condition=models.Q(
                    appointment__isnull=False,
                    status__in=["new", "reviewed"],
                ),
                name="one_open_change_request_per_appointment",
            ),
        ]

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Portal request client must belong to the same practice."})
        if self.appointment_id:
            if self.appointment.practice_id != self.practice_id:
                raise ValidationError({"appointment": "Portal request appointment must belong to the same practice."})
            if self.appointment.client_id != self.client_id:
                raise ValidationError({"appointment": "Portal request appointment must belong to the same client."})

    def __str__(self):
        return f"{self.get_category_display()} from {self.client}"


class PortalConversation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="portal_conversations")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="portal_conversations")
    subject = models.CharField(max_length=160)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="started_portal_conversations")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_portal_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Conversation client must belong to the same practice."})

    def __str__(self):
        return f"{self.subject} ({self.client})"


class PortalMessage(models.Model):
    class AuthorKind(models.TextChoices):
        CLIENT = "client", "Client"
        STAFF = "staff", "Practice team"

    conversation = models.ForeignKey(PortalConversation, on_delete=models.CASCADE, related_name="messages")
    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="portal_messages")
    author = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_messages")
    author_kind = models.CharField(max_length=20, choices=AuthorKind.choices)
    body = models.TextField(max_length=10000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        if self.conversation_id and self.practice_id and self.conversation.practice_id != self.practice_id:
            raise ValidationError({"practice": "Message must belong to the conversation practice."})

    def __str__(self):
        return f"{self.get_author_kind_display()} message in {self.conversation}"


class PublicBookingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="public_booking_requests")
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="public_booking_requests")
    appointment = models.ForeignKey("appointments.Appointment", on_delete=models.SET_NULL, null=True, blank=True, related_name="public_booking_requests")
    approved_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_booking_requests")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    requested_starts_at = models.DateTimeField()
    requested_ends_at = models.DateTimeField()
    appointment_type = models.CharField(max_length=20, choices=Appointment.AppointmentType.choices, default=Appointment.AppointmentType.VIDEO)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        errors = {}
        if self.requested_starts_at and self.requested_ends_at and self.requested_ends_at <= self.requested_starts_at:
            errors["requested_ends_at"] = "Requested appointment must end after it starts."
        if self.requested_starts_at and self.requested_starts_at < timezone.now():
            errors["requested_starts_at"] = "Choose a future appointment time."
        if self.practice_id and self.requested_starts_at and self.requested_ends_at:
            if not practice_allows_interval(self.practice, self.requested_starts_at, self.requested_ends_at):
                errors["requested_starts_at"] = "Choose a time within the practice working hours."
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "Booking request client must belong to the same practice."
        if self.appointment_id and self.practice_id and self.appointment.practice_id != self.practice_id:
            errors["appointment"] = "Booking request appointment must belong to the same practice."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Booking request from {self.first_name} {self.last_name}"


class IntakePacketTemplate(models.Model):
    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="intake_templates")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    questions = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "name"], name="unique_intake_template_name_per_practice"),
        ]

    def clean(self):
        if not self.questions:
            raise ValidationError({"questions": "Add at least one intake question."})

    def __str__(self):
        return self.name


class ClientIntakeAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="intake_assignments")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="intake_assignments")
    template = models.ForeignKey(IntakePacketTemplate, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_intakes")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    answers = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_intakes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        errors = {}
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "Intake client must belong to the same practice."
        if self.template_id and self.practice_id and self.template.practice_id != self.practice_id:
            errors["template"] = "Intake template must belong to the same practice."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.template} for {self.client}"
