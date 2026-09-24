from django.core.exceptions import ValidationError
from django.db import models


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
        BILLING = "billing", "Billing question"
        DOCUMENT = "document", "Document question"
        GENERAL = "general", "General message"

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="portal_requests")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="portal_requests")
    submitted_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_requests")
    category = models.CharField(max_length=30, choices=Category.choices)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Portal request client must belong to the same practice."})

    def __str__(self):
        return f"{self.get_category_display()} from {self.client}"


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
