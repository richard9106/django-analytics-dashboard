from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.billing.models import InsurancePayer, InsuranceRate, Invoice, PackageUsage, Payment, PracticeSubscription, ServicePackage
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

        self.appointment.status = Appointment.Status.COMPLETED
        self.appointment.save(update_fields=["status"])
        PackageUsage.objects.create(
            package=package,
            appointment=self.appointment,
            quantity=1,
            used_at=timezone.now(),
        )

        package.refresh_from_db()
        self.assertEqual(package.sessions_used, 1)
        self.assertEqual(package.sessions_remaining, 3)

    def test_scheduled_or_cancelled_appointment_cannot_consume_package(self):
        package = ServicePackage.objects.create(
            practice=self.practice, client=self.client, name="4 session package",
            sessions_purchased=4, total_price=Decimal("500.00"), purchased_at=timezone.localdate(),
        )
        usage = PackageUsage(package=package, appointment=self.appointment, quantity=1, used_at=timezone.now())
        with self.assertRaisesMessage(ValidationError, "Scheduled appointments"):
            usage.full_clean()

        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])
        with self.assertRaisesMessage(ValidationError, "Cancelled appointments"):
            usage.full_clean()

    def test_no_show_requires_explicit_charge_reason(self):
        package = ServicePackage.objects.create(
            practice=self.practice, client=self.client, name="4 session package",
            sessions_purchased=4, total_price=Decimal("500.00"), purchased_at=timezone.localdate(),
        )
        self.appointment.status = Appointment.Status.NO_SHOW
        self.appointment.save(update_fields=["status"])
        usage = PackageUsage(package=package, appointment=self.appointment, quantity=1, used_at=timezone.now())
        with self.assertRaisesMessage(ValidationError, "No-show appointments"):
            usage.full_clean()

        usage.charge_reason = PackageUsage.ChargeReason.NO_SHOW
        usage.full_clean()

    def test_package_usage_rejects_other_client_appointment(self):
        other_client = Client.objects.create(practice=self.practice, first_name="Lucia", last_name="Garcia")
        other_appointment = Appointment.objects.create(
            practice=self.practice,
            client=other_client,
            therapist=self.therapist,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
            status=Appointment.Status.COMPLETED,
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

    def test_invoice_actions_are_grouped_in_floating_kebab_menu_with_csrf(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-ACTIONS",
            amount=Decimal("150.00"), status=Invoice.Status.DRAFT,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("billing:list"))

        self.assertContains(response, '<th><span class="sr-only">Actions</span></th>', html=True)
        self.assertContains(response, 'class="invoice-actions-trigger"')
        self.assertContains(response, 'aria-controls="invoice-actions-')
        self.assertContains(response, 'role="menu"')
        self.assertNotContains(response, '<details class="invoice-actions">')
        self.assertNotContains(response, 'invoice-actions-menu-title')
        self.assertContains(response, 'data-confirm-message="Publish this invoice to make it available for billing?"')
        self.assertContains(response, 'data-confirm-message="Delete this draft invoice? This cannot be undone."')
        self.assertContains(response, "Print invoice")
        self.assertContains(response, "Publish")
        self.assertContains(response, "Delete draft")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_invoice_action_menu_includes_keyboard_and_mobile_behavior(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        Invoice.objects.create(practice=practice, client=client, invoice_number="INV-BEHAVIOR", amount=Decimal("150.00"))

        self.client.force_login(user)
        response = self.client.get(reverse("billing:list"))

        self.assertContains(response, "document.body.appendChild(menu)")
        self.assertContains(response, "event.key === 'Escape'")
        self.assertContains(response, "is-mobile-sheet")
        self.assertContains(response, "trigger.focus()")

    def test_invoice_action_menu_honors_billing_permissions(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        profile = UserProfile.objects.get(user=user)
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {
            "billing": {"view": True, "create": False, "edit": False, "delete": False},
        }
        profile.save(update_fields=["role", "permissions"])
        Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-RESTRICTED",
            amount=Decimal("150.00"), status=Invoice.Status.DRAFT,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("billing:list"))

        self.assertContains(response, "Print invoice")
        self.assertNotContains(response, "Edit invoice")
        self.assertNotContains(response, "Publish")
        self.assertNotContains(response, "Delete draft")

    def test_therapist_without_billing_view_cannot_open_billing_documents(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        profile = UserProfile.objects.get(user=user)
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {"billing": {"view": False, "create": False, "edit": False, "delete": False}}
        profile.save(update_fields=["role", "permissions"])
        invoice = Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-THERAPIST", amount=Decimal("150.00")
        )

        self.client.force_login(user)
        for url in (
            reverse("billing:list"),
            reverse("billing:invoice_print", args=[invoice.pk]),
            reverse("billing:invoice_superbill", args=[invoice.pk]),
            reverse("settings:package_templates"),
            reverse("settings:insurance"),
        ):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_therapist_billing_view_permission_hides_mutation_controls_and_blocks_mutations(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        profile = UserProfile.objects.get(user=user)
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {"billing": {"view": True, "create": False, "edit": False, "delete": False}}
        profile.save(update_fields=["role", "permissions"])
        invoice = Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-VIEW-ONLY", amount=Decimal("150.00")
        )
        package_template = SessionPackageTemplate.objects.create(
            practice=practice, name="View-only template", sessions_included=4, price=Decimal("520.00")
        )
        payer = InsurancePayer.objects.create(practice=practice, name="View-only payer")
        rate = InsuranceRate.objects.create(
            practice=practice, payer=payer, state="CA",
            service_code=InsuranceRate.ServiceCode.PSYCHOTHERAPY_60,
            reimbursement_amount=Decimal("150.00"),
        )

        self.client.force_login(user)
        billing_response = self.client.get(reverse("billing:list"))
        self.assertContains(billing_response, "Print invoice")
        self.assertNotContains(billing_response, "+ New invoice")
        self.assertNotContains(billing_response, "+ Session package")

        templates_response = self.client.get(reverse("settings:package_templates"))
        self.assertContains(templates_response, package_template.name)
        self.assertNotContains(templates_response, "+ Package template")
        self.assertNotContains(templates_response, "Edit template")

        insurance_response = self.client.get(reverse("settings:insurance"))
        self.assertContains(insurance_response, payer.name)
        self.assertNotContains(insurance_response, "+ Rate")
        self.assertNotContains(insurance_response, "+ Custom payer")
        self.assertNotContains(insurance_response, "Edit payer")

        mutation_urls = (
            reverse("billing:invoice_create"),
            reverse("billing:package_create"),
            reverse("settings:package_template_create"),
            reverse("settings:package_template_edit", args=[package_template.pk]),
            reverse("settings:package_template_delete", args=[package_template.pk]),
            reverse("settings:insurance_payer_create"),
            reverse("settings:insurance_payer_edit", args=[payer.pk]),
            reverse("settings:insurance_payer_delete", args=[payer.pk]),
            reverse("settings:insurance_rate_create"),
            reverse("settings:insurance_rate_edit", args=[rate.pk]),
            reverse("settings:insurance_rate_delete", args=[rate.pk]),
        )
        for url in mutation_urls:
            self.assertEqual(self.client.post(url).status_code, 302, url)

    def test_manual_payment_records_partial_balance_for_invoice(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            invoice_number="INV-PARTIAL",
            amount=Decimal("100.00"),
            status=Invoice.Status.SENT,
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:payment_create"), {
            "invoice": invoice.pk,
            "amount": "40.00",
            "method": Payment.Method.CASH,
            "paid_at": "2026-09-29T10:00",
            "external_payment_id": "cash-receipt-1",
        })

        self.assertRedirects(response, reverse("billing:list"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.SENT)
        self.assertEqual(invoice.balance_due, Decimal("60.00"))
        self.assertEqual(Payment.objects.get().method, Payment.Method.CASH)

    def test_full_manual_payment_marks_invoice_paid(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            invoice_number="INV-FULL",
            amount=Decimal("100.00"),
            status=Invoice.Status.SENT,
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:payment_create"), {
            "invoice": invoice.pk,
            "amount": "100.00",
            "method": Payment.Method.ACH,
            "paid_at": "2026-09-29T10:00",
            "external_payment_id": "ach-1",
        })

        self.assertRedirects(response, reverse("billing:list"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(invoice.paid_at)

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

    def test_draft_invoice_can_be_published_once_and_is_audited(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-PUBLISH", amount=Decimal("150.00")
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:invoice_publish", args=[invoice.pk]))

        self.assertRedirects(response, reverse("billing:list"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.SENT)
        self.assertEqual(invoice.published_by, user)
        self.assertIsNotNone(invoice.published_at)
        log = AuditLog.objects.get(object_type="billing.Invoice", object_id=str(invoice.pk))
        self.assertEqual(log.metadata["event"], "published")

    def test_published_invoice_cannot_be_edited_or_deleted(self):
        user, practice, _therapist, client, _appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-LOCKED", amount=Decimal("150.00"), status=Invoice.Status.SENT
        )
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("billing:invoice_edit", args=[invoice.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("billing:invoice_delete", args=[invoice.pk])).status_code, 404)

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

    def test_invoice_print_view_is_scoped_and_audited(self):
        user, practice, _therapist, client, appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            appointment=appointment,
            invoice_number="INV-PRINT",
            amount=Decimal("150.00"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("billing:invoice_print", args=[invoice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-PRINT")
        self.assertContains(response, "Print / Save PDF")
        log = AuditLog.objects.get(action=AuditLog.Action.EXPORT, object_type="billing.Invoice")
        self.assertEqual(log.metadata["document_type"], "invoice")

    def test_invoice_superbill_view_includes_service_details(self):
        user, practice, _therapist, client, appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            appointment=appointment,
            invoice_number="INV-SUPER",
            amount=Decimal("150.00"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("billing:invoice_superbill", args=[invoice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Superbill")
        self.assertContains(response, "Provider / Service Information")
        self.assertContains(response, appointment.get_appointment_type_display())

    def test_invoice_print_view_rejects_other_practice_invoice(self):
        user, _practice, _therapist, _client, _appointment = self.create_practice_user()
        _other_user, other_practice, _other_therapist, other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        invoice = Invoice.objects.create(
            practice=other_practice,
            client=other_client,
            invoice_number="INV-HIDDEN",
            amount=Decimal("150.00"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("billing:invoice_print", args=[invoice.pk]))

        self.assertEqual(response.status_code, 404)

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

    def test_insurance_settings_requires_login(self):
        response = self.client.get(reverse("settings:insurance"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('settings:insurance')}")

    def test_insurance_settings_shows_common_payers_and_scoped_rates(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        payer = InsurancePayer.objects.create(practice=practice, name="Visible payer")
        InsuranceRate.objects.create(
            practice=practice,
            payer=payer,
            state="CA",
            service_code=InsuranceRate.ServiceCode.PSYCHOTHERAPY_60,
            reimbursement_amount=Decimal("150.00"),
        )
        other_user, other_practice, _other_therapist, _other_client, _other_appointment = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        other_payer = InsurancePayer.objects.create(practice=other_practice, name="Hidden payer")
        InsuranceRate.objects.create(
            practice=other_practice,
            payer=other_payer,
            state="NY",
            service_code=InsuranceRate.ServiceCode.PSYCHOTHERAPY_45,
            reimbursement_amount=Decimal("90.00"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("settings:insurance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insurance")
        self.assertContains(response, "Visible payer")
        self.assertNotContains(response, "Hidden payer")

    def test_insurance_payer_and_rate_create_save_to_practice(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("settings:insurance_payer_create"), {
            "name": "Local Health Plan",
            "payer_id": "LHP001",
            "active": "on",
            "notes": "Contracted payer.",
        })

        self.assertRedirects(response, reverse("settings:insurance"))
        payer = InsurancePayer.objects.get(name="Local Health Plan")
        self.assertEqual(payer.practice, practice)

        response = self.client.post(reverse("settings:insurance_rate_create"), {
            "payer": payer.pk,
            "state": "ca",
            "service_code": InsuranceRate.ServiceCode.PSYCHOTHERAPY_60,
            "service_label": "Individual therapy",
            "reimbursement_amount": "175.00",
            "active": "on",
            "notes": "Practice contracted amount.",
        })

        self.assertRedirects(response, reverse("settings:insurance"))
        rate = InsuranceRate.objects.get()
        self.assertEqual(rate.practice, practice)
        self.assertEqual(rate.state, "CA")
        self.assertEqual(rate.reimbursement_amount, Decimal("175.00"))

    def test_subscribe_missing_stripe_config_redirects_to_pricing(self):
        user, _practice, _therapist, _client, _appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.get(reverse("billing:subscribe", args=["solo", "monthly"]))

        self.assertRedirects(response, reverse("pricing"))

    def test_subscribe_success_and_cancel_pages_render(self):
        user, _practice, _therapist, _client, _appointment = self.create_practice_user()

        self.client.force_login(user)
        success_response = self.client.get(reverse("billing:subscribe_success"))
        cancel_response = self.client.get(reverse("billing:subscribe_cancel"))

        self.assertEqual(success_response.status_code, 200)
        self.assertContains(success_response, "Your 15-day trial is starting")
        self.assertContains(success_response, f"{reverse('dashboard')}?tour=1")
        self.assertEqual(cancel_response.status_code, 200)
        self.assertContains(cancel_response, "Checkout was canceled")

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    @patch("apps.billing.views.stripe.billing_portal.Session.create")
    def test_customer_portal_redirects_to_stripe_for_practice_subscription(self, mock_create):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.SOLO,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.TRIALING,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        mock_create.return_value = SimpleNamespace(url="https://billing.stripe.test/session")

        self.client.force_login(user)
        response = self.client.post(reverse("billing:customer_portal"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://billing.stripe.test/session")
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["customer"], "cus_123")
        self.assertIn(reverse("profile_settings"), kwargs["return_url"])

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    def test_customer_portal_without_customer_redirects_to_profile(self):
        user, _practice, _therapist, _client, _appointment = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("billing:customer_portal"))

        self.assertRedirects(response, reverse("profile_settings"))

    @override_settings(
        STRIPE_SECRET_KEY="stripe-secret-placeholder",
        STRIPE_PRICE_IDS={
            "solo": {"monthly": "price_solo_monthly", "yearly": "price_solo_yearly"},
            "group": {"monthly": "price_group_monthly", "yearly": "price_group_yearly"},
            "clinic": {"monthly": "price_clinic_monthly", "yearly": "price_clinic_yearly"},
        },
    )
    @patch("apps.billing.views.stripe.Subscription.modify")
    @patch("apps.billing.views.stripe.Subscription.retrieve")
    def test_change_plan_updates_existing_stripe_subscription(self, mock_retrieve, mock_modify):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        subscription = PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.SOLO,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.ACTIVE,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            stripe_price_id="price_solo_monthly",
        )
        mock_retrieve.return_value = {"items": {"data": [{"id": "si_123"}]}}

        self.client.force_login(user)
        response = self.client.post(reverse("billing:change_plan", args=["group", "yearly"]))

        self.assertRedirects(response, reverse("profile_settings"))
        mock_retrieve.assert_called_once_with("sub_123")
        mock_modify.assert_called_once_with(
            "sub_123",
            items=[{"id": "si_123", "price": "price_group_yearly"}],
            proration_behavior="create_prorations",
            metadata={"practice_id": str(practice.pk), "plan": "group", "period": "yearly"},
        )
        subscription.refresh_from_db()
        self.assertEqual(subscription.plan, PracticeSubscription.Plan.GROUP)
        self.assertEqual(subscription.billing_period, PracticeSubscription.BillingPeriod.YEARLY)
        self.assertEqual(subscription.stripe_price_id, "price_group_yearly")

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    def test_change_plan_blocks_downgrade_when_internal_users_exceed_target_limit(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        second_user = get_user_model().objects.create_user(username="second")
        UserProfile.objects.create(user=second_user, practice=practice, role=UserProfile.Role.ADMIN)
        third_user = get_user_model().objects.create_user(username="third")
        UserProfile.objects.create(user=third_user, practice=practice, role=UserProfile.Role.ADMIN)
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.GROUP,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.ACTIVE,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:change_plan", args=["solo", "monthly"]))

        self.assertRedirects(response, reverse("profile_settings"))
        subscription = PracticeSubscription.objects.get(practice=practice)
        self.assertEqual(subscription.plan, PracticeSubscription.Plan.GROUP)

    def test_change_plan_without_stripe_subscription_redirects_to_checkout(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.SOLO,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.INCOMPLETE,
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:change_plan", args=["group", "monthly"]))

        self.assertRedirects(response, reverse("billing:subscribe", args=["group", "monthly"]), fetch_redirect_response=False)

    @override_settings(
        STRIPE_SECRET_KEY="stripe-secret-placeholder",
        STRIPE_PRICE_IDS={
            "solo": {"monthly": "price_solo_monthly", "yearly": "price_solo_yearly"},
            "group": {"monthly": "price_group_monthly", "yearly": "price_group_yearly"},
            "clinic": {"monthly": "price_clinic_monthly", "yearly": "price_clinic_yearly"},
        },
    )
    @patch("apps.billing.views.stripe.Invoice.create_preview")
    @patch("apps.billing.views.stripe.Subscription.retrieve")
    def test_plan_preview_returns_stripe_proration_estimate(self, mock_retrieve, mock_upcoming):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.SOLO,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.ACTIVE,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            stripe_price_id="price_solo_monthly",
        )
        mock_retrieve.return_value = {"items": {"data": [{"id": "si_123"}]}}
        mock_upcoming.return_value = {
            "currency": "usd",
            "subtotal": 5900,
            "amount_due": 3900,
            "lines": {"data": [{"amount": -2000}, {"amount": 5900}]},
        }

        self.client.force_login(user)
        response = self.client.post(reverse("billing:plan_preview", args=["group", "monthly"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["amount_due"], "USD 39.00")
        self.assertEqual(response.json()["subtotal"], "USD 59.00")
        self.assertEqual(response.json()["credit"], "USD 20.00")
        mock_upcoming.assert_called_once_with(
            customer="cus_123",
            subscription="sub_123",
            subscription_details={
                "items": [{"id": "si_123", "price": "price_group_monthly"}],
                "proration_behavior": "create_prorations",
            },
        )

    def test_plan_preview_blocks_downgrade_when_internal_users_exceed_target_limit(self):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        second_user = get_user_model().objects.create_user(username="second")
        UserProfile.objects.create(user=second_user, practice=practice, role=UserProfile.Role.ADMIN)
        third_user = get_user_model().objects.create_user(username="third")
        UserProfile.objects.create(user=third_user, practice=practice, role=UserProfile.Role.ADMIN)
        PracticeSubscription.objects.create(
            practice=practice,
            plan=PracticeSubscription.Plan.GROUP,
            billing_period=PracticeSubscription.BillingPeriod.MONTHLY,
            status=PracticeSubscription.Status.ACTIVE,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("billing:plan_preview", args=["solo", "monthly"]))

        self.assertEqual(response.status_code, 400)
        self.assertIn("allows up to 1", response.json()["error"])

    @override_settings(
        STRIPE_SECRET_KEY="stripe-secret-placeholder",
        STRIPE_PRICE_IDS={
            "solo": {"monthly": "price_solo_monthly", "yearly": ""},
            "group": {"monthly": "", "yearly": ""},
            "clinic": {"monthly": "", "yearly": ""},
        },
    )
    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_subscribe_creates_checkout_session_for_practice(self, mock_create):
        user, practice, _therapist, _client, _appointment = self.create_practice_user()
        mock_create.return_value = SimpleNamespace(url="https://checkout.stripe.test/session")

        self.client.force_login(user)
        response = self.client.get(reverse("billing:subscribe", args=["solo", "monthly"]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.stripe.test/session")
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["line_items"], [{"price": "price_solo_monthly", "quantity": 1}])
        self.assertEqual(kwargs["payment_method_collection"], "always")
        self.assertEqual(kwargs["subscription_data"]["trial_period_days"], 15)
        self.assertEqual(kwargs["metadata"]["practice_id"], str(practice.pk))
        subscription = PracticeSubscription.objects.get(practice=practice)
        self.assertEqual(subscription.plan, PracticeSubscription.Plan.SOLO)
        self.assertEqual(subscription.billing_period, PracticeSubscription.BillingPeriod.MONTHLY)
        self.assertEqual(subscription.status, PracticeSubscription.Status.INCOMPLETE)

    @override_settings(
        STRIPE_WEBHOOK_SECRET="webhook-secret-placeholder",
        STRIPE_PRICE_IDS={
            "solo": {"monthly": "price_solo_monthly", "yearly": ""},
            "group": {"monthly": "", "yearly": ""},
            "clinic": {"monthly": "", "yearly": ""},
        },
    )
    @patch("apps.billing.views.stripe.Webhook.construct_event")
    def test_subscription_updated_webhook_syncs_practice_subscription(self, mock_construct_event):
        _user, practice, _therapist, _client, _appointment = self.create_practice_user()
        period_end = int((timezone.now() + timedelta(days=30)).timestamp())
        mock_construct_event.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123",
                    "status": "active",
                    "metadata": {"practice_id": str(practice.pk)},
                    "current_period_end": period_end,
                    "items": {"data": [{"price": {"id": "price_solo_monthly"}}]},
                }
            },
        }

        response = self.client.post(
            reverse("billing:stripe_webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, 200)
        subscription = PracticeSubscription.objects.get(practice=practice)
        self.assertEqual(subscription.plan, PracticeSubscription.Plan.SOLO)
        self.assertEqual(subscription.billing_period, PracticeSubscription.BillingPeriod.MONTHLY)
        self.assertEqual(subscription.status, PracticeSubscription.Status.ACTIVE)
        self.assertEqual(subscription.stripe_customer_id, "cus_123")
        self.assertEqual(subscription.stripe_subscription_id, "sub_123")

    @override_settings(STRIPE_WEBHOOK_SECRET="webhook-secret-placeholder")
    @patch("apps.billing.views.stripe.Webhook.construct_event")
    def test_invoice_checkout_webhook_marks_matching_invoice_paid(self, mock_construct_event):
        _user, practice, _therapist, client, _appointment = self.create_practice_user()
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            invoice_number="INV-PAY-001",
            amount=Decimal("120.00"),
            status=Invoice.Status.SENT,
        )
        mock_construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "payment_status": "paid",
                    "metadata": {
                        "invoice_id": str(invoice.pk),
                        "practice_id": str(practice.pk),
                        "client_id": str(client.pk),
                    },
                }
            },
        }

        response = self.client.post(
            reverse("billing:stripe_webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(invoice.paid_at)
