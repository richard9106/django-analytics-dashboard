from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="invoices")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="invoices")
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    package = models.ForeignKey(
        "billing.ServicePackage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=40)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "invoice_number"], name="unique_invoice_number_per_practice")
        ]

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount < Decimal("0.00"):
            errors["amount"] = "Invoice amount cannot be negative."
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "Invoice client must belong to the same practice."
        if self.appointment_id:
            if self.appointment.practice_id != self.practice_id:
                errors["appointment"] = "Invoice appointment must belong to the same practice."
            if self.appointment.client_id != self.client_id:
                errors["appointment"] = "Invoice appointment must match the invoice client."
        if self.package_id:
            if self.package.practice_id != self.practice_id:
                errors["package"] = "Invoice package must belong to the same practice."
            if self.package.client_id != self.client_id:
                errors["package"] = "Invoice package must match the invoice client."
        if self.status == self.Status.PAID and not self.paid_at:
            errors["paid_at"] = "Paid invoices must include paid_at."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.invoice_number} - {self.client}"


class ServicePackage(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Refunded"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="service_packages")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="service_packages")
    template = models.ForeignKey(
        "billing.SessionPackageTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_packages",
    )
    name = models.CharField(max_length=120)
    sessions_purchased = models.PositiveIntegerField()
    sessions_used = models.PositiveIntegerField(default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    purchased_at = models.DateField()
    expires_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-purchased_at", "-created_at"]

    @property
    def sessions_remaining(self):
        return max(self.sessions_purchased - self.sessions_used, 0)

    def clean(self):
        errors = {}
        if self.sessions_purchased <= 0:
            errors["sessions_purchased"] = "Package must include at least one session."
        if self.sessions_used > self.sessions_purchased:
            errors["sessions_used"] = "Used sessions cannot exceed purchased sessions."
        if self.total_price is not None and self.total_price < Decimal("0.00"):
            errors["total_price"] = "Package price cannot be negative."
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "Package client must belong to the same practice."
        if self.template_id and self.practice_id and self.template.practice_id != self.practice_id:
            errors["template"] = "Package template must belong to the same practice."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} - {self.client}"


class SessionPackageTemplate(models.Model):
    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="session_package_templates")
    name = models.CharField(max_length=120)
    sessions_included = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "name"], name="unique_session_package_template_per_practice")
        ]

    def clean(self):
        errors = {}
        if self.sessions_included <= 0:
            errors["sessions_included"] = "Template must include at least one session."
        if self.price is not None and self.price < Decimal("0.00"):
            errors["price"] = "Template price cannot be negative."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.sessions_included} sessions)"


class PackageUsage(models.Model):
    package = models.ForeignKey(ServicePackage, on_delete=models.CASCADE, related_name="usages")
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.CASCADE, related_name="package_usage")
    quantity = models.PositiveIntegerField(default=1)
    used_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-used_at"]

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors["quantity"] = "Usage quantity must be greater than zero."
        if self.package_id and self.appointment_id:
            if self.package.status != ServicePackage.Status.ACTIVE:
                errors["package"] = "Only active packages can be used for sessions."
            if self.package.expires_at and self.package.expires_at < timezone.localdate():
                errors["package"] = "Expired packages cannot be used for sessions."
            if self.appointment.practice_id != self.package.practice_id:
                errors["appointment"] = "Usage appointment must belong to the same practice as the package."
            if self.appointment.client_id != self.package.client_id:
                errors["appointment"] = "Usage appointment must match the package client."
            existing_usage = self.package.usages.exclude(pk=self.pk).aggregate(total=models.Sum("quantity"))["total"] or 0
            if existing_usage + self.quantity > self.package.sessions_purchased:
                errors["quantity"] = "Package does not have enough remaining sessions."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        used = self.package.usages.aggregate(total=models.Sum("quantity"))["total"] or 0
        self.package.sessions_used = used
        if used >= self.package.sessions_purchased and self.package.status == ServicePackage.Status.ACTIVE:
            self.package.status = ServicePackage.Status.COMPLETED
        self.package.save(update_fields=["sessions_used", "status", "updated_at"])

    def delete(self, *args, **kwargs):
        package = self.package
        result = super().delete(*args, **kwargs)
        used = package.usages.aggregate(total=models.Sum("quantity"))["total"] or 0
        package.sessions_used = used
        if package.status == ServicePackage.Status.COMPLETED and used < package.sessions_purchased:
            package.status = ServicePackage.Status.ACTIVE
        package.save(update_fields=["sessions_used", "status", "updated_at"])
        return result

    def __str__(self):
        return f"{self.package} used for {self.appointment}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        ACH = "ach", "ACH"
        INSURANCE = "insurance", "Insurance"
        OTHER = "other", "Other"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="payments")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CARD)
    external_payment_id = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= Decimal("0.00"):
            errors["amount"] = "Payment amount must be greater than zero."
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            errors["client"] = "Payment client must belong to the same practice."
        if self.invoice_id:
            if self.invoice.practice_id != self.practice_id:
                errors["invoice"] = "Payment invoice must belong to the same practice."
            if self.invoice.client_id != self.client_id:
                errors["invoice"] = "Payment invoice must match the payment client."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.client} payment {self.amount}"
