from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.billing.models import Invoice, PackageUsage, Payment, ServicePackage
from apps.billing.models import SessionPackageTemplate
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

    def test_service_package_tracks_remaining_sessions(self):
        package = ServicePackage.objects.create(
            practice=self.practice,
            client=self.client,
            name="4 session package",
            sessions_purchased=4,
            sessions_used=1,
            total_price=Decimal("500.00"),
            purchased_at=timezone.localdate(),
        )

        self.assertEqual(package.sessions_remaining, 3)

    def test_package_usage_updates_used_sessions(self):
        package = ServicePackage.objects.create(
            practice=self.practice,
            client=self.client,
            name="4 session package",
            sessions_purchased=4,
            total_price=Decimal("500.00"),
            purchased_at=timezone.localdate(),
        )

        PackageUsage.objects.create(
            package=package,
            appointment=self.appointment,
            quantity=1,
            used_at=timezone.now(),
        )

        package.refresh_from_db()
        self.assertEqual(package.sessions_used, 1)
        self.assertEqual(package.sessions_remaining, 3)

    def test_package_usage_rejects_other_client_appointment(self):
        other_client = Client.objects.create(practice=self.practice, first_name="Lucia", last_name="Garcia")
        other_appointment = Appointment.objects.create(
            practice=self.practice,
            client=other_client,
            therapist=self.therapist,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
        )
        package = ServicePackage.objects.create(
            practice=self.practice,
            client=self.client,
            name="4 session package",
            sessions_purchased=4,
            total_price=Decimal("500.00"),
            purchased_at=timezone.localdate(),
        )
        usage = PackageUsage(package=package, appointment=other_appointment, quantity=1, used_at=timezone.now())

        with self.assertRaisesMessage(ValidationError, "must match the package client"):
            usage.full_clean()


class BillingViewTests(TestCase):
    def create_practice_user(self, username="drsmith", practice_name="NuviaMy Wellness"):
        user = get_user_model().objects.create_user(
            username=username,
            password="StrongPass123!",
            first_name="Laura",
            last_name="Smith",
        )
        practice = Practice.objects.create(name=practice_name)
        therapist = TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number=f"{username}-12345",
            license_state="CA",
        )
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        starts_at = timezone.now() + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        return user, practice, therapist, client, appointment

    def test_billing_list_requires_login(self):
        response = self.client.get(reverse("billing:list"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('billing:list')}")

    def test_billing_list_is_scoped_and_shows_package_data(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        _other_user, other_practice, _other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        package = ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="4 session package",
            sessions_purchased=4,
            sessions_used=1,
            total_price=Decimal("500.00"),
            purchased_at=timezone.localdate(),
        )
        Invoice.objects.create(practice=practice, client=client, package=package, invoice_number="INV-100", amount=Decimal("500.00"))
        Invoice.objects.create(practice=other_practice, client=other_client, invoice_number="INV-HIDDEN", amount=Decimal("100.00"))

        self.client.force_login(user)
        response = self.client.get(reverse("billing:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Billing Workspace")
        self.assertContains(response, "INV-100")
        self.assertContains(response, "4 session package")
        self.assertContains(response, "1 of 4 used")
        self.assertContains(response, 'id="invoice-create-modal"')
        self.assertContains(response, 'id="package-create-modal"')
        self.assertNotContains(response, "INV-HIDDEN")

    def test_invoice_create_saves_to_user_practice(self):
        user, practice, _therapist, client, appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("billing:invoice_create"), {
            "client": client.pk,
            "appointment": appointment.pk,
            "package": "",
            "invoice_number": "INV-101",
            "amount": "150.00",
            "status": Invoice.Status.PAID,
            "due_date": "",
            "paid_at": "",
            "notes": "Session invoice.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.practice, practice)
        self.assertIsNotNone(invoice.paid_at)

    def test_invoice_create_auto_generates_package_invoice_number(self):
        user, _practice, _therapist, client, _appointment = self.create_practice_user()
        package = ServicePackage.objects.create(
            practice=client.practice,
            client=client,
            name="4 session package",
            sessions_purchased=4,
            total_price=Decimal("520.00"),
            purchased_at=timezone.localdate(),
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:invoice_create"), {
            "client": client.pk,
            "appointment": "",
            "package": package.pk,
            "invoice_number": "",
            "amount": "520.00",
            "status": Invoice.Status.DRAFT,
            "due_date": "",
            "paid_at": "",
            "notes": "Package invoice.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        invoice = Invoice.objects.get()
        expected_prefix = f"PKG-{package.pk}-{timezone.localdate():%Y%m%d}-"
        self.assertEqual(invoice.invoice_number, f"{expected_prefix}0001")

    def test_invoice_create_autofills_client_and_amount_from_package(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        package = ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="4 session package",
            sessions_purchased=4,
            total_price=Decimal("520.00"),
            purchased_at=timezone.localdate(),
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:invoice_create"), {
            "client": "",
            "appointment": "",
            "package": package.pk,
            "invoice_number": "",
            "amount": "",
            "status": Invoice.Status.DRAFT,
            "due_date": "",
            "paid_at": "",
            "notes": "Package invoice.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.client, client)
        self.assertEqual(invoice.amount, Decimal("520.00"))

    def test_invoice_create_auto_generates_sequential_package_invoice_number(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        package = ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="4 session package",
            sessions_purchased=4,
            total_price=Decimal("520.00"),
            purchased_at=timezone.localdate(),
        )
        prefix = f"PKG-{package.pk}-{timezone.localdate():%Y%m%d}"
        Invoice.objects.create(
            practice=practice,
            client=client,
            package=package,
            invoice_number=f"{prefix}-0001",
            amount=Decimal("520.00"),
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:invoice_create"), {
            "client": client.pk,
            "appointment": "",
            "package": package.pk,
            "invoice_number": "",
            "amount": "520.00",
            "status": Invoice.Status.DRAFT,
            "due_date": "",
            "paid_at": "",
            "notes": "Second package invoice.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        self.assertTrue(Invoice.objects.filter(invoice_number=f"{prefix}-0002").exists())

    def test_package_create_saves_to_user_practice(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("billing:package_create"), {
            "client": client.pk,
            "name": "3 session package",
            "sessions_purchased": 3,
            "sessions_used": 0,
            "total_price": "420.00",
            "status": ServicePackage.Status.ACTIVE,
            "purchased_at": timezone.localdate().isoformat(),
            "expires_at": "",
            "notes": "Prepaid sessions.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        package = ServicePackage.objects.get()
        self.assertEqual(package.practice, practice)
        self.assertEqual(package.sessions_remaining, 3)

    def test_expired_package_cannot_be_used_for_session(self):
        _user, practice, _therapist, client, appointment = self.create_practice_user()
        package = ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="Expired package",
            sessions_purchased=4,
            total_price=Decimal("520.00"),
            purchased_at=timezone.localdate() - timedelta(days=30),
            expires_at=timezone.localdate() - timedelta(days=1),
        )
        usage = PackageUsage(package=package, appointment=appointment, quantity=1, used_at=timezone.now())

        with self.assertRaisesMessage(ValidationError, "Expired packages cannot be used"):
            usage.full_clean()

    def test_completed_package_cannot_be_used_for_session(self):
        _user, practice, _therapist, client, appointment = self.create_practice_user()
        package = ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="Completed package",
            sessions_purchased=4,
            sessions_used=4,
            total_price=Decimal("520.00"),
            status=ServicePackage.Status.COMPLETED,
            purchased_at=timezone.localdate(),
        )
        usage = PackageUsage(package=package, appointment=appointment, quantity=1, used_at=timezone.now())

        with self.assertRaisesMessage(ValidationError, "Only active packages can be used"):
            usage.full_clean()

    def test_package_create_can_use_template(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        template = SessionPackageTemplate.objects.create(
            practice=practice,
            name="4 prepaid sessions",
            sessions_included=4,
            price=Decimal("520.00"),
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:package_create"), {
            "client": client.pk,
            "template": template.pk,
            "name": template.name,
            "sessions_purchased": template.sessions_included,
            "sessions_used": 0,
            "total_price": template.price,
            "status": ServicePackage.Status.ACTIVE,
            "purchased_at": timezone.localdate().isoformat(),
            "expires_at": "",
            "notes": "Template package.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        package = ServicePackage.objects.get()
        self.assertEqual(package.template, template)
        self.assertEqual(package.sessions_remaining, 4)

    def test_settings_package_template_list_requires_login(self):
        response = self.client.get(reverse("settings:package_templates"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('settings:package_templates')}")

    def test_settings_package_templates_are_scoped(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        _other_user, other_practice, _other_therapist, _other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        SessionPackageTemplate.objects.create(
            practice=practice,
            name="Visible package",
            sessions_included=4,
            price=Decimal("520.00"),
        )
        SessionPackageTemplate.objects.create(
            practice=other_practice,
            name="Hidden package",
            sessions_included=3,
            price=Decimal("390.00"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("settings:package_templates"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session Package Templates")
        self.assertContains(response, "Visible package")
        self.assertNotContains(response, "Hidden package")

    def test_settings_package_template_create_saves_to_user_practice(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("settings:package_template_create"), {
            "name": "6 session package",
            "sessions_included": 6,
            "price": "720.00",
            "description": "Six prepaid sessions.",
            "active": "on",
        })

        self.assertRedirects(response, reverse("settings:package_templates"))
        template = SessionPackageTemplate.objects.get()
        self.assertEqual(template.practice, practice)
        self.assertEqual(template.sessions_included, 6)
