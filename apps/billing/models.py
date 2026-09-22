from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


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
        if self.status == self.Status.PAID and not self.paid_at:
            errors["paid_at"] = "Paid invoices must include paid_at."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.invoice_number} - {self.client}"


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
