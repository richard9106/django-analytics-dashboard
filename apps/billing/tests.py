from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.billing.models import Invoice, Payment
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile


class BillingModelTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name="NuviaMy Wellness")
        self.user = get_user_model().objects.create_user(username="drsmith")
        self.therapist = TherapistProfile.objects.create(
            user=self.user,
            practice=self.practice,
            license_number="ABC123",
            license_state="CA",
        )
        self.client = Client.objects.create(practice=self.practice, first_name="Ana", last_name="Perez")
        starts_at = timezone.now() + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            practice=self.practice,
            client=self.client,
            therapist=self.therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

    def test_invoice_accepts_matching_practice_client_and_appointment(self):
        invoice = Invoice(
            practice=self.practice,
            client=self.client,
            appointment=self.appointment,
            invoice_number="INV-001",
            amount=Decimal("150.00"),
        )

        invoice.full_clean()

    def test_invoice_rejects_other_practice_client(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_client = Client.objects.create(practice=other_practice, first_name="Luis", last_name="Diaz")
        invoice = Invoice(
            practice=self.practice,
            client=other_client,
            invoice_number="INV-002",
            amount=Decimal("150.00"),
        )

        with self.assertRaisesMessage(ValidationError, "same practice"):
            invoice.full_clean()

    def test_paid_invoice_requires_paid_at(self):
        invoice = Invoice(
            practice=self.practice,
            client=self.client,
            invoice_number="INV-003",
            amount=Decimal("150.00"),
            status=Invoice.Status.PAID,
        )

        with self.assertRaisesMessage(ValidationError, "paid_at"):
            invoice.full_clean()

    def test_payment_requires_matching_invoice_client(self):
        other_client = Client.objects.create(practice=self.practice, first_name="Lucia", last_name="Garcia")
        invoice = Invoice.objects.create(
            practice=self.practice,
            client=other_client,
            invoice_number="INV-004",
            amount=Decimal("150.00"),
        )
        payment = Payment(
            practice=self.practice,
            client=self.client,
            invoice=invoice,
            amount=Decimal("50.00"),
            paid_at=timezone.now(),
        )

        with self.assertRaisesMessage(ValidationError, "must match"):
            payment.full_clean()
