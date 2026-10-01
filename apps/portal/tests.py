from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import stripe

from apps.appointments.models import Appointment
from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.billing.models import Invoice, ServicePackage
from apps.clients.models import Client
from apps.documents.models import ClientDocument
from apps.portal.models import ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate, PortalConversation, PortalMessage, PublicBookingRequest
from apps.practices.models import Practice, TherapistProfile


class ClientPortalAccessModelTests(TestCase):
    def test_portal_access_rejects_client_from_other_practice(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        other_practice = Practice.objects.create(name="Other Clinic")
        user = get_user_model().objects.create_user(username="clientuser")
        client = Client.objects.create(practice=other_practice, first_name="Ana", last_name="Perez")
        access = ClientPortalAccess(user=user, practice=practice, client=client)

        with self.assertRaisesMessage(ValidationError, "same practice"):
            access.full_clean()

    def test_portal_access_defaults_active(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        user = get_user_model().objects.create_user(username="clientuser")
        client = Client.objects.create(practice=practice, first_name="Ana", last_name="Perez")
        access = ClientPortalAccess(user=user, practice=practice, client=client)

        access.full_clean()
        self.assertTrue(access.is_active)


class ClientPortalViewTests(TestCase):
    def setUp(self):
        cache.clear()

    def create_portal_user(self, username="clientuser", practice_name="NuviaMy Wellness"):
        practice = Practice.objects.create(name=practice_name)
        therapist_user = get_user_model().objects.create_user(username=f"{username}-therapist")
        therapist = TherapistProfile.objects.create(
            user=therapist_user,
            practice=practice,
            license_number=f"{username}-LIC",
            license_state="CA",
        )
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="StrongPass123!",
            first_name="Maya",
        )
        access = ClientPortalAccess.objects.create(user=user, practice=practice, client=client, is_active=True)
        return user, practice, therapist, client, access

    def test_portal_dashboard_requires_login(self):
        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('portal:dashboard')}")

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    @patch("apps.portal.views.stripe.checkout.Session.create")
    def test_client_can_open_stripe_checkout_for_own_invoice(self, mock_create):
        user, practice, _therapist, client, _access = self.create_portal_user()
        practice.stripe_connect_account_id = "acct_practice"
        practice.stripe_connect_charges_enabled = True
        practice.stripe_connect_payouts_enabled = True
        practice.save(update_fields=["stripe_connect_account_id", "stripe_connect_charges_enabled", "stripe_connect_payouts_enabled"])
        client.email = "maya@example.com"
        client.save(update_fields=["email"])
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            invoice_number="INV-PAY-001",
            amount=Decimal("120.00"),
            status=Invoice.Status.SENT,
        )
        mock_create.return_value = SimpleNamespace(url="https://checkout.stripe.test/invoice")

        self.client.force_login(user)
        response = self.client.post(reverse("portal:invoice_pay", args=[invoice.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.stripe.test/invoice")
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 12000)
        self.assertEqual(kwargs["customer_email"], "maya@example.com")
        self.assertEqual(kwargs["payment_intent_data"]["transfer_data"]["destination"], "acct_practice")
        self.assertEqual(kwargs["metadata"]["invoice_id"], str(invoice.pk))

    def test_portal_hides_draft_and_only_offers_sent_or_overdue_invoices(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        Invoice.objects.create(practice=practice, client=client, invoice_number="INV-DRAFT", amount=Decimal("120.00"))
        Invoice.objects.create(practice=practice, client=client, invoice_number="INV-SENT", amount=Decimal("120.00"), status=Invoice.Status.SENT)
        Invoice.objects.create(practice=practice, client=client, invoice_number="INV-OVERDUE", amount=Decimal("80.00"), status=Invoice.Status.OVERDUE)

        self.client.force_login(user)
        response = self.client.get(reverse("portal:dashboard"))

        self.assertContains(response, "INV-SENT")
        self.assertContains(response, "INV-OVERDUE")
        self.assertContains(response, 'role="region" aria-labelledby="portal-open-invoices-heading"')
        self.assertContains(response, 'id="portal-open-invoices-scroll-help"')
        self.assertContains(response, '<th scope="col">Invoice</th>', html=True)
        self.assertContains(response, "dialog._returnFocus")
        self.assertContains(response, "labelPortalDialogs")
        self.assertNotContains(response, "INV-DRAFT")

    def test_portal_explains_when_client_payments_are_not_ready(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-NOT-READY",
            amount=Decimal("120.00"), status=Invoice.Status.SENT,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("portal:dashboard"))

        self.assertContains(response, "Online payment is not available yet.")
        self.assertNotContains(response, "Pay invoice")

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    @patch("apps.portal.views.stripe.checkout.Session.create")
    def test_portal_shows_stripe_payment_error_after_redirect(self, mock_create):
        user, practice, _therapist, client, _access = self.create_portal_user()
        practice.stripe_connect_account_id = "acct_practice"
        practice.stripe_connect_charges_enabled = True
        practice.stripe_connect_payouts_enabled = True
        practice.save(update_fields=["stripe_connect_account_id", "stripe_connect_charges_enabled", "stripe_connect_payouts_enabled"])
        invoice = Invoice.objects.create(
            practice=practice, client=client, invoice_number="INV-STRIPE-ERROR",
            amount=Decimal("120.00"), status=Invoice.Status.SENT,
        )
        mock_create.side_effect = stripe.error.StripeError("checkout unavailable")

        self.client.force_login(user)
        response = self.client.post(reverse("portal:invoice_pay", args=[invoice.pk]), follow=True)

        self.assertContains(response, "Stripe could not open payment checkout.")
        self.assertContains(response, "role=\"alert\"")

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    @patch("apps.portal.views.stripe.checkout.Session.create")
    def test_portal_cannot_pay_a_draft_invoice(self, mock_create):
        user, practice, _therapist, client, _access = self.create_portal_user()
        invoice = Invoice.objects.create(practice=practice, client=client, invoice_number="INV-DRAFT-PAY", amount=Decimal("120.00"))

        self.client.force_login(user)
        response = self.client.post(reverse("portal:invoice_pay", args=[invoice.pk]))

        self.assertRedirects(response, reverse("portal:dashboard"))
        mock_create.assert_not_called()

    @override_settings(STRIPE_SECRET_KEY="stripe-secret-placeholder")
    @patch("apps.portal.views.stripe.checkout.Session.create")
    def test_client_cannot_pay_another_clients_invoice(self, mock_create):
        user, practice, _therapist, client, _access = self.create_portal_user()
        other_client = Client.objects.create(practice=practice, first_name="Other", last_name="Client")
        invoice = Invoice.objects.create(
            practice=practice,
            client=other_client,
            invoice_number="INV-HIDDEN-PAY",
            amount=Decimal("120.00"),
            status=Invoice.Status.SENT,
        )

        self.client.force_login(user)
        response = self.client.post(reverse("portal:invoice_pay", args=[invoice.pk]))

        self.assertEqual(response.status_code, 404)
        mock_create.assert_not_called()

    def test_non_portal_user_is_forbidden(self):
        user = get_user_model().objects.create_user(username="therapist", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_inactive_portal_user_is_forbidden(self):
        user, _practice, _therapist, _client, access = self.create_portal_user()
        access.is_active = False
        access.save()
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_portal_dashboard_is_scoped_to_linked_client(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        other_client = Client.objects.create(practice=practice, first_name="Hidden", last_name="Client")
        starts_at = timezone.now() + timedelta(days=1)
        Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        Appointment.objects.create(
            practice=practice,
            client=other_client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        Invoice.objects.create(practice=practice, client=client, invoice_number="INV-VISIBLE", amount=Decimal("120.00"), status=Invoice.Status.SENT)
        Invoice.objects.create(practice=practice, client=other_client, invoice_number="INV-HIDDEN", amount=Decimal("120.00"))
        ServicePackage.objects.create(
            practice=practice,
            client=client,
            name="4 session package",
            sessions_purchased=4,
            sessions_used=1,
            total_price=Decimal("520.00"),
            purchased_at=timezone.localdate(),
        )
        ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Visible document",
            file="visible.txt",
            visible_to_client=True,
        )
        ClientDocument.objects.create(
            practice=practice,
            client=client,
            title="Internal document",
            file="internal.txt",
            visible_to_client=False,
        )
        ClientDocument.objects.create(
            practice=practice,
            client=other_client,
            title="Hidden document",
            file="hidden.txt",
            visible_to_client=True,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome")
        self.assertContains(response, "INV-VISIBLE")
        self.assertContains(response, "4 session package")
        self.assertContains(response, "3 of 4 sessions remaining")
        self.assertContains(response, "Visible document")
        self.assertNotContains(response, "INV-HIDDEN")
        self.assertNotContains(response, "Hidden Client")
        self.assertNotContains(response, "Internal document")
        self.assertNotContains(response, "Hidden document")

    def test_portal_client_can_create_request(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        self.client.force_login(user)

        response = self.client.post(reverse("portal:request_create"), {
            "category": ClientPortalRequest.Category.RESCHEDULE,
            "subject": "Need a different time",
            "message": "Could we move next week's session?",
        })

        self.assertRedirects(response, reverse("portal:dashboard"))
        portal_request = ClientPortalRequest.objects.get()
        self.assertEqual(portal_request.practice, practice)
        self.assertEqual(portal_request.client, client)
        self.assertEqual(portal_request.submitted_by, user)
        self.assertEqual(portal_request.status, ClientPortalRequest.Status.NEW)
        log = AuditLog.objects.get(action=AuditLog.Action.CREATE, object_type="portal.ClientPortalRequest")
        self.assertEqual(log.metadata["client_id"], client.pk)
        self.assertEqual(log.metadata["category"], ClientPortalRequest.Category.RESCHEDULE)

    def test_portal_client_can_start_a_secure_conversation(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        self.client.force_login(user)

        response = self.client.post(reverse("portal:conversations"), {
            "subject": "Question about my invoice",
            "body": "Could you confirm the due date?",
        })

        self.assertRedirects(response, reverse("portal:conversations"))
        conversation = PortalConversation.objects.get()
        self.assertEqual(conversation.practice, practice)
        self.assertEqual(conversation.client, client)
        message = conversation.messages.get()
        self.assertEqual(message.author, user)
        self.assertEqual(message.author_kind, PortalMessage.AuthorKind.CLIENT)
        self.assertEqual(message.body, "Could you confirm the due date?")
        self.assertTrue(AuditLog.objects.filter(object_type="portal.PortalMessage", object_id=str(message.pk)).exists())

    def test_portal_client_cannot_read_another_clients_conversation(self):
        user, practice, _therapist, _client, _access = self.create_portal_user()
        _other_user, _other_practice, _other_therapist, other_client, _other_access = self.create_portal_user(
            username="other-client", practice_name="Other Practice",
        )
        conversation = PortalConversation.objects.create(
            practice=other_client.practice,
            client=other_client,
            subject="Private conversation",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("portal:conversation_detail", args=[conversation.public_id]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(conversation.practice_id, other_client.practice_id)

    def test_practice_can_reply_and_resolve_a_conversation(self):
        _client_user, practice, _therapist, client, _access = self.create_portal_user()
        owner = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=owner, practice=practice, role=UserProfile.Role.OWNER)
        conversation = PortalConversation.objects.create(practice=practice, client=client, subject="Billing question")
        PortalMessage.objects.create(
            conversation=conversation,
            practice=practice,
            author_kind=PortalMessage.AuthorKind.CLIENT,
            body="Can you help?",
        )

        self.client.force_login(owner)
        response = self.client.post(reverse("portal_requests:conversation_detail", args=[conversation.public_id]), {"body": "Yes, we can help."})

        self.assertRedirects(response, reverse("portal_requests:conversation_detail", args=[conversation.public_id]))
        reply = conversation.messages.get(author_kind=PortalMessage.AuthorKind.STAFF)
        self.assertEqual(reply.author, owner)
        response = self.client.post(reverse("portal_requests:conversation_detail", args=[conversation.public_id]), {"action": "status", "status": "resolved"})
        self.assertRedirects(response, reverse("portal_requests:conversation_detail", args=[conversation.public_id]))
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, PortalConversation.Status.RESOLVED)
        self.assertEqual(conversation.resolved_by, owner)

    def test_client_message_bell_counts_and_marks_staff_replies_read(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        conversation = PortalConversation.objects.create(practice=practice, client=client, subject="Update")
        message = PortalMessage.objects.create(
            conversation=conversation, practice=practice,
            author_kind=PortalMessage.AuthorKind.STAFF, body="Your practice replied.",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))
        self.assertContains(response, "1 unread messages")
        self.assertContains(response, ">1</strong>")
        self.client.get(reverse("portal:conversation_detail", args=[conversation.public_id]))

        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_staff_message_badge_counts_unread_client_messages(self):
        _client_user, practice, _therapist, client, _access = self.create_portal_user()
        owner = get_user_model().objects.create_user(username="message-owner", password="StrongPass123!")
        UserProfile.objects.create(user=owner, practice=practice, role=UserProfile.Role.OWNER)
        conversation = PortalConversation.objects.create(practice=practice, client=client, subject="Question")
        PortalMessage.objects.create(
            conversation=conversation, practice=practice,
            author_kind=PortalMessage.AuthorKind.CLIENT, body="I need help.",
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("portal_requests:conversations"))

        self.assertContains(response, "Secure messages, 1 unread")
        self.assertContains(response, ">1</strong>")

    def test_portal_client_can_request_appointment_change(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        starts_at = timezone.now() + timedelta(days=2)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        self.client.force_login(user)

        response = self.client.post(reverse("portal:appointment_change_request", args=[appointment.pk]), {
            "category": ClientPortalRequest.Category.RESCHEDULE,
            "message": "Can we move this to Friday afternoon?",
        })

        self.assertRedirects(response, reverse("portal:dashboard"))
        portal_request = ClientPortalRequest.objects.get()
        self.assertEqual(portal_request.appointment, appointment)
        self.assertEqual(portal_request.practice, practice)
        self.assertEqual(portal_request.client, client)
        self.assertIn("Appointment change request", portal_request.subject)

    def test_appointment_change_request_shows_success_confirmation(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        appointment = Appointment.objects.create(
            practice=practice, client=client, therapist=therapist,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("portal:appointment_change_request", args=[appointment.pk]),
            {"category": ClientPortalRequest.Category.RESCHEDULE, "message": "Friday afternoon would work."},
            follow=True,
        )

        self.assertContains(response, "Your appointment change request was sent to the practice.")
        self.assertEqual(ClientPortalRequest.objects.filter(appointment=appointment).count(), 1)

    def test_invalid_appointment_change_request_keeps_errors_and_reopens_modal(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        appointment = Appointment.objects.create(
            practice=practice, client=client, therapist=therapist,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("portal:appointment_change_request", args=[appointment.pk]),
            {"category": ClientPortalRequest.Category.RESCHEDULE, "message": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "This field is required.", status_code=400)
        self.assertContains(response, f"appointment-change-{appointment.pk}", status_code=400)
        self.assertContains(response, f"openPortalDialog(document.getElementById('appointment-change-{appointment.pk}'))", status_code=400)
        self.assertFalse(ClientPortalRequest.objects.filter(appointment=appointment).exists())

    def test_only_one_open_appointment_change_request_is_allowed(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        appointment = Appointment.objects.create(
            practice=practice, client=client, therapist=therapist,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
        )
        self.client.force_login(user)
        payload = {"category": ClientPortalRequest.Category.CANCELLATION, "message": "I can no longer attend."}
        self.client.post(reverse("portal:appointment_change_request", args=[appointment.pk]), payload)

        response = self.client.post(reverse("portal:appointment_change_request", args=[appointment.pk]), payload)

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "already has an open change request", status_code=400)
        self.assertEqual(ClientPortalRequest.objects.filter(appointment=appointment).count(), 1)

    def test_appointment_change_modal_clarifies_reschedule_and_cancellation(self):
        user, practice, therapist, client, _access = self.create_portal_user()
        appointment = Appointment.objects.create(
            practice=practice, client=client, therapist=therapist,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, minutes=50),
        )
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))

        self.assertContains(response, "Reschedule — request a different appointment time")
        self.assertContains(response, "Cancel — ask the practice to cancel this appointment")

    def test_portal_client_cannot_request_change_for_other_client_appointment(self):
        user, _practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        _other_user, other_practice, other_therapist, other_client, _other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        starts_at = timezone.now() + timedelta(days=2)
        appointment = Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.post(reverse("portal:appointment_change_request", args=[appointment.pk]), {
            "category": ClientPortalRequest.Category.RESCHEDULE,
            "message": "Should not work.",
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ClientPortalRequest.objects.count(), 0)

    def test_portal_dashboard_shows_only_linked_client_requests(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        other_client = Client.objects.create(practice=practice, first_name="Hidden", last_name="Client")
        ClientPortalRequest.objects.create(
            practice=practice,
            client=client,
            submitted_by=user,
            category=ClientPortalRequest.Category.BILLING,
            subject="Visible request",
            message="Question about invoice.",
        )
        ClientPortalRequest.objects.create(
            practice=practice,
            client=other_client,
            category=ClientPortalRequest.Category.GENERAL,
            subject="Hidden request",
            message="Should not show.",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("portal:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible request")
        self.assertNotContains(response, "Hidden request")

    def test_practice_can_create_and_assign_intake_packet(self):
        _portal_user, practice, _therapist, client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        self.client.force_login(practice_user)

        response = self.client.post(reverse("intake:template_create"), {
            "name": "New client intake",
            "description": "Before first visit",
            "active": "on",
            "question_lines": "What brings you to therapy?\nEmergency contact name",
        })

        self.assertRedirects(response, reverse("intake:list"))
        template = IntakePacketTemplate.objects.get()
        self.assertEqual(template.practice, practice)
        self.assertEqual(template.questions, ["What brings you to therapy?", "Emergency contact name"])

        response = self.client.post(reverse("intake:assign"), {"client": client.pk, "template": template.pk})

        self.assertRedirects(response, reverse("intake:list"))
        assignment = ClientIntakeAssignment.objects.get()
        self.assertEqual(assignment.practice, practice)
        self.assertEqual(assignment.client, client)
        self.assertEqual(assignment.status, ClientIntakeAssignment.Status.ASSIGNED)

    def test_portal_client_can_complete_assigned_intake_packet(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        template = IntakePacketTemplate.objects.create(
            practice=practice,
            name="New client intake",
            questions=["What brings you to therapy?", "Emergency contact name"],
        )
        assignment = ClientIntakeAssignment.objects.create(practice=practice, client=client, template=template)
        self.client.force_login(user)

        response = self.client.get(reverse("portal:dashboard"))
        self.assertContains(response, "New client intake")
        self.assertContains(response, reverse("portal:intake_complete", args=[assignment.pk]))

        response = self.client.post(reverse("portal:intake_complete", args=[assignment.pk]), {
            "question_0": "Anxiety and stress.",
            "question_1": "Sam Johnson",
        })

        self.assertRedirects(response, reverse("portal:dashboard"))
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ClientIntakeAssignment.Status.SUBMITTED)
        self.assertEqual(assignment.answers["question_0"]["answer"], "Anxiety and stress.")
        self.assertIsNotNone(assignment.submitted_at)

    def test_portal_client_cannot_complete_other_clients_intake(self):
        user, _practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        _other_user, other_practice, _other_therapist, other_client, _other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        template = IntakePacketTemplate.objects.create(practice=other_practice, name="Hidden intake", questions=["Hidden question"])
        assignment = ClientIntakeAssignment.objects.create(practice=other_practice, client=other_client, template=template)

        self.client.force_login(user)
        response = self.client.get(reverse("portal:intake_complete", args=[assignment.pk]))

        self.assertEqual(response.status_code, 404)

    def test_practice_can_mark_submitted_intake_reviewed(self):
        _portal_user, practice, _therapist, client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        template = IntakePacketTemplate.objects.create(practice=practice, name="New client intake", questions=["Question"])
        assignment = ClientIntakeAssignment.objects.create(
            practice=practice,
            client=client,
            template=template,
            status=ClientIntakeAssignment.Status.SUBMITTED,
            answers={"question_0": {"question": "Question", "answer": "Answer"}},
        )

        self.client.force_login(practice_user)
        response = self.client.post(reverse("intake:review", args=[assignment.pk]))

        self.assertRedirects(response, reverse("intake:list"))
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ClientIntakeAssignment.Status.REVIEWED)
        self.assertEqual(assignment.reviewed_by, practice_user)

    def test_practice_dashboard_shows_portal_request_task(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        ClientPortalRequest.objects.create(
            practice=practice,
            client=client,
            submitted_by=user,
            category=ClientPortalRequest.Category.DOCUMENT,
            subject="Document question",
            message="Can you share the consent form?",
        )

        self.client.force_login(practice_user)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client portal requests")
        self.assertContains(response, "1 portal request awaiting follow-up")

    def test_practice_can_view_portal_requests_with_sidebar_badge(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        ClientPortalRequest.objects.create(
            practice=practice,
            client=client,
            submitted_by=user,
            category=ClientPortalRequest.Category.BILLING,
            subject="Billing question",
            message="Can you explain this invoice?",
        )

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_requests:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Requests")
        self.assertContains(response, "Billing question")
        self.assertContains(response, f"/book/{practice.public_booking_slug}/")
        self.assertContains(response, 'data-copy-button')
        self.assertContains(response, 'Copy link')
        self.assertNotContains(response, f'href="http://testserver/book/{practice.public_booking_slug}/"')
        self.assertContains(response, "Unique slug")
        self.assertContains(response, 'class="nav-badge">1</strong>')

    def test_practice_can_update_portal_request_status(self):
        user, practice, _therapist, client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        portal_request = ClientPortalRequest.objects.create(
            practice=practice,
            client=client,
            submitted_by=user,
            category=ClientPortalRequest.Category.DOCUMENT,
            subject="Document question",
            message="Can you share a copy?",
        )

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_requests:status", args=[portal_request.pk]), {"status": ClientPortalRequest.Status.RESOLVED})

        portal_request.refresh_from_db()
        self.assertRedirects(response, reverse("portal_requests:list"))
        self.assertEqual(portal_request.status, ClientPortalRequest.Status.RESOLVED)
        log = AuditLog.objects.get(action=AuditLog.Action.UPDATE, object_type="portal.ClientPortalRequest")
        self.assertEqual(log.object_id, str(portal_request.pk))
        self.assertEqual(log.metadata["status"], ClientPortalRequest.Status.RESOLVED)

    def test_portal_request_status_update_is_scoped_to_practice(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        other_user, other_practice, _other_therapist, other_client, _other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        portal_request = ClientPortalRequest.objects.create(
            practice=other_practice,
            client=other_client,
            submitted_by=other_user,
            category=ClientPortalRequest.Category.GENERAL,
            subject="Hidden request",
            message="Should not update.",
        )
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_requests:status", args=[portal_request.pk]), {"status": ClientPortalRequest.Status.RESOLVED})

        portal_request.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(portal_request.status, ClientPortalRequest.Status.NEW)

    def test_client_cannot_open_practice_requests_page(self):
        user, practice, _therapist, _client, _access = self.create_portal_user()
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.CLIENT)

        self.client.force_login(user)
        response = self.client.get(reverse("portal_requests:list"))

        self.assertRedirects(response, reverse("portal:dashboard"))

    def test_public_booking_page_accepts_appointment_request(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user()
        starts_at = timezone.localtime().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=3)

        response = self.client.post(reverse("public_booking", args=[practice.public_booking_slug]), {
            "first_name": "Jordan",
            "last_name": "Rivera",
            "email": "jordan@example.com",
            "phone": "555-0101",
            "requested_starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "appointment_type": Appointment.AppointmentType.VIDEO,
            "reason": "I would like an intake appointment.",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request received")
        booking_request = PublicBookingRequest.objects.get(practice=practice, email="jordan@example.com")
        self.assertEqual(booking_request.status, PublicBookingRequest.Status.PENDING)
        self.assertEqual(timezone.localtime(booking_request.requested_starts_at).strftime("%H:%M"), "14:00")

    def test_public_booking_is_rate_limited(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user()
        for _ in range(5):
            response = self.client.post(reverse("public_booking", args=[practice.public_booking_slug]), {})
            self.assertEqual(response.status_code, 400)

        response = self.client.post(reverse("public_booking", args=[practice.public_booking_slug]), {})

        self.assertEqual(response.status_code, 429)

    def test_practice_can_approve_public_booking_request(self):
        _user, practice, therapist, _client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        starts_at = timezone.localtime().replace(hour=15, minute=0, second=0, microsecond=0) + timedelta(days=4)
        booking_request = PublicBookingRequest.objects.create(
            practice=practice,
            first_name="Jordan",
            last_name="Rivera",
            email="jordan@example.com",
            phone="555-0101",
            requested_starts_at=starts_at,
            requested_ends_at=starts_at + timedelta(minutes=50),
            appointment_type=Appointment.AppointmentType.PHONE,
        )

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_requests:booking_approve", args=[booking_request.pk]))

        self.assertRedirects(response, reverse("portal_requests:list"))
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, PublicBookingRequest.Status.APPROVED)
        self.assertIsNotNone(booking_request.client)
        self.assertIsNotNone(booking_request.appointment)
        self.assertEqual(booking_request.client.primary_therapist, therapist)
        self.assertEqual(booking_request.appointment.appointment_type, Appointment.AppointmentType.PHONE)

    def test_public_booking_approval_is_scoped_to_practice(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        _other_user, other_practice, _other_therapist, _other_client, _other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        starts_at = timezone.localtime().replace(hour=13, minute=0, second=0, microsecond=0) + timedelta(days=5)
        booking_request = PublicBookingRequest.objects.create(
            practice=other_practice,
            first_name="Hidden",
            last_name="Client",
            email="hidden@example.com",
            requested_starts_at=starts_at,
            requested_ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_requests:booking_approve", args=[booking_request.pk]))

        booking_request.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(booking_request.status, PublicBookingRequest.Status.PENDING)
        self.assertFalse(Appointment.objects.filter(practice=other_practice, client__email="hidden@example.com").exists())

    def test_practice_can_decline_public_booking_request(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user()
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2)
        booking_request = PublicBookingRequest.objects.create(
            practice=practice,
            first_name="Jordan",
            last_name="Rivera",
            email="jordan@example.com",
            requested_starts_at=starts_at,
            requested_ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_requests:booking_decline", args=[booking_request.pk]))

        self.assertRedirects(response, reverse("portal_requests:list"))
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, PublicBookingRequest.Status.DECLINED)

    def test_portal_settings_list_requires_login(self):
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('portal_settings:portal_access')}")

    def test_portal_settings_list_is_scoped_to_practice(self):
        user, practice, _therapist, client, _access = self.create_portal_user(username="practice-client")
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        other_user, _other_practice, _other_therapist, _other_client, _other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, client.first_name)
        self.assertContains(response, user.username)
        self.assertNotContains(response, other_user.username)

    def test_portal_settings_create_access(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_settings:portal_access_create"), {
            "client": client.pk,
            "username": "maya.portal",
            "email": "maya@example.com",
            "password": "StrongPass123!",
            "is_active": "on",
        })

        self.assertRedirects(response, reverse("portal_settings:portal_access"))
        access = ClientPortalAccess.objects.get()
        self.assertEqual(access.client, client)
        self.assertTrue(access.is_active)
        self.assertTrue(access.user.check_password("StrongPass123!"))
        self.assertTrue(access.user.nuvia_profile.must_change_password)

    def test_portal_settings_suggests_client_email_unique_username_and_password(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        get_user_model().objects.create_user(username="maya.johnson")
        Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson", email="maya@example.com")

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-email="maya@example.com"')
        self.assertContains(response, 'data-username="maya.johnson.2"')
        self.assertContains(response, 'data-password="Nuvia-')

    def test_portal_settings_rejects_duplicate_username_case_insensitive(self):
        practice = Practice.objects.create(name="NuviaMy Wellness")
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        get_user_model().objects.create_user(username="Maya.Portal")

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_settings:portal_access_create"), {
            "client": client.pk,
            "username": "maya.portal",
            "email": "maya@example.com",
            "password": "StrongPass123!",
            "is_active": "on",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with this username already exists.")
        self.assertFalse(ClientPortalAccess.objects.exists())

    def test_portal_settings_update_is_scoped_to_practice(self):
        _user, _practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        other_user, other_practice, _other_therapist, _other_client, other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        practice_user = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=Practice.objects.get(name="NuviaMy Wellness"), role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access_edit", args=[other_access.pk]))

        self.assertEqual(response.status_code, 404)

    def test_portal_settings_shows_last_login(self):
        user, practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        user.last_login = timezone.make_aware(datetime(2026, 9, 23, 15, 30))
        user.save(update_fields=["last_login"])
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Last login:")
        self.assertNotContains(response, "Last login: Never")

    def test_portal_settings_reset_password_creates_temporary_credentials_and_audit_log(self):
        user, practice, _therapist, client, access = self.create_portal_user(username="practice-client")
        old_password = user.password
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_settings:portal_access_reset_password", args=[access.pk]), follow=True)

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(user.password, old_password)
        self.assertTrue(user.nuvia_profile.must_change_password)
        self.assertContains(response, "Temporary credentials")
        self.assertContains(response, "Portal URL:")
        self.assertContains(response, user.username)
        log = AuditLog.objects.get(action=AuditLog.Action.UPDATE, object_type="portal.ClientPortalAccess")
        self.assertEqual(log.object_id, str(access.pk))
        self.assertEqual(log.metadata["client_id"], client.pk)
        self.assertTrue(log.metadata["password_reset"])

    def test_portal_settings_password_reset_requires_confirmation(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.get(reverse("portal_settings:portal_access"))

        self.assertContains(response, "Reset password")
        self.assertContains(response, "data-confirm-message=\"Reset this client's portal password? Their current password will stop working.\"")

    def test_portal_settings_reset_password_is_scoped_to_practice(self):
        _user, practice, _therapist, _client, _access = self.create_portal_user(username="practice-client")
        _other_user, _other_practice, _other_therapist, _other_client, other_access = self.create_portal_user(
            username="other-client",
            practice_name="Other Practice",
        )
        practice_user = get_user_model().objects.create_user(username="practice-owner", password="StrongPass123!")
        UserProfile.objects.create(user=practice_user, practice=practice, role=UserProfile.Role.OWNER)

        self.client.force_login(practice_user)
        response = self.client.post(reverse("portal_settings:portal_access_reset_password", args=[other_access.pk]))

        self.assertEqual(response.status_code, 404)

    def test_client_with_temporary_password_is_forced_to_change_password(self):
        user, _practice, _therapist, _client, _access = self.create_portal_user()
        UserProfile.objects.create(user=user, practice=_practice, role=UserProfile.Role.CLIENT, must_change_password=True)

        self.client.force_login(user)
        response = self.client.get(reverse("portal:dashboard"))

        self.assertRedirects(response, reverse("force_password_change"))

    def test_client_login_with_temporary_password_redirects_to_password_change(self):
        user, practice, _therapist, _client, _access = self.create_portal_user()
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.CLIENT, must_change_password=True)

        response = self.client.post(reverse("login"), {
            "username": user.email,
            "password": "StrongPass123!",
        })

        self.assertRedirects(response, reverse("force_password_change"))

    def test_client_password_change_clears_required_flag(self):
        user, practice, _therapist, _client, _access = self.create_portal_user()
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.CLIENT, must_change_password=True)
        self.client.force_login(user)

        response = self.client.post(reverse("force_password_change"), {
            "new_password1": "NewStrongPass123!",
            "new_password2": "NewStrongPass123!",
        })

        user.refresh_from_db()
        self.assertRedirects(response, reverse("portal:dashboard"))
        self.assertFalse(user.nuvia_profile.must_change_password)
        self.assertTrue(user.check_password("NewStrongPass123!"))
