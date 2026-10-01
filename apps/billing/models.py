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
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_invoices",
    )
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

    @property
    def payment_total(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def balance_due(self):
        return max(self.amount - self.payment_total, Decimal('0.00'))


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


class InsurancePayer(models.Model):
    practice = models.ForeignKey(
        "practices.Practice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="insurance_payers",
    )
    name = models.CharField(max_length=140)
    payer_id = models.CharField(max_length=80, blank=True)
    is_system_template = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "name"], name="unique_insurance_payer_per_practice"),
        ]

    def __str__(self):
        return self.name


class InsuranceRate(models.Model):
    class ServiceCode(models.TextChoices):
        INTAKE = "90791", "90791 - Psychiatric diagnostic evaluation"
        PSYCHOTHERAPY_45 = "90834", "90834 - Psychotherapy, 45 minutes"
        PSYCHOTHERAPY_60 = "90837", "90837 - Psychotherapy, 60 minutes"
        FAMILY = "90847", "90847 - Family psychotherapy"
        GROUP = "90853", "90853 - Group psychotherapy"
        CRISIS = "90839", "90839 - Psychotherapy for crisis"
        OTHER = "other", "Other"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="insurance_rates")
    payer = models.ForeignKey(InsurancePayer, on_delete=models.CASCADE, related_name="rates")
    state = models.CharField(max_length=2)
    service_code = models.CharField(max_length=20, choices=ServiceCode.choices)
    service_label = models.CharField(max_length=160, blank=True)
    reimbursement_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state", "payer__name", "service_code"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "payer", "state", "service_code"], name="unique_insurance_rate_per_state_service"),
        ]

    def clean(self):
        errors = {}
        if self.payer_id and self.practice_id and self.payer.practice_id and self.payer.practice_id != self.practice_id:
            errors["payer"] = "Insurance payer must be global or belong to the same practice."
        if self.reimbursement_amount is not None and self.reimbursement_amount < Decimal("0.00"):
            errors["reimbursement_amount"] = "Reimbursement amount cannot be negative."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.payer} {self.state} {self.service_code}"


class PackageUsage(models.Model):
    class ChargeReason(models.TextChoices):
        COMPLETED = "completed", "Completed session"
        NO_SHOW = "no_show", "Approved no-show charge"

    package = models.ForeignKey(ServicePackage, on_delete=models.CASCADE, related_name="usages")
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.CASCADE, related_name="package_usage")
    quantity = models.PositiveIntegerField(default=1)
    charge_reason = models.CharField(max_length=20, choices=ChargeReason.choices, default=ChargeReason.COMPLETED)
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
            if self.appointment.status == self.appointment.Status.CANCELLED:
                errors["appointment"] = "Cancelled appointments cannot consume package sessions."
            elif self.appointment.status == self.appointment.Status.SCHEDULED:
                errors["appointment"] = "Scheduled appointments cannot consume package sessions."
            elif self.appointment.status == self.appointment.Status.NO_SHOW and self.charge_reason != self.ChargeReason.NO_SHOW:
                errors["charge_reason"] = "No-show appointments require an approved no-show charge reason."
            elif self.appointment.status == self.appointment.Status.COMPLETED and self.charge_reason != self.ChargeReason.COMPLETED:
                errors["charge_reason"] = "Completed appointments require a completed session charge reason."
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
        return f"{self.package} used for {self.appointment} ({self.get_charge_reason_display()})"


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


class PracticeSubscription(models.Model):
    PLAN_INTERNAL_USER_LIMITS = {
        "solo": 1,
        "group": 5,
        "clinic": 15,
    }

    class Plan(models.TextChoices):
        SOLO = "solo", "Solo Therapist"
        GROUP = "group", "Group Practice"
        CLINIC = "clinic", "Clinic"

    class BillingPeriod(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"

    practice = models.OneToOneField("practices.Practice", on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=20, choices=Plan.choices)
    billing_period = models.CharField(max_length=20, choices=BillingPeriod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INCOMPLETE)
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True)
    stripe_price_id = models.CharField(max_length=120, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["practice__name"]

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def internal_user_limit(self):
        return self.internal_user_limit_for_plan(self.plan)

    @classmethod
    def internal_user_limit_for_plan(cls, plan):
        return cls.PLAN_INTERNAL_USER_LIMITS[plan]

    @property
    def internal_user_count(self):
        return self.practice.user_profiles.exclude(role__in=["client", "owner"]).count()

    @property
    def internal_user_slots_remaining(self):
        return max(self.internal_user_limit - self.internal_user_count, 0)

    def can_add_internal_user(self, exclude_profile_id=None):
        profiles = self.practice.user_profiles.exclude(role__in=["client", "owner"])
        if exclude_profile_id:
            profiles = profiles.exclude(pk=exclude_profile_id)
        return profiles.count() < self.internal_user_limit

    def __str__(self):
        return f"{self.practice} - {self.get_plan_display()} ({self.get_status_display()})"
