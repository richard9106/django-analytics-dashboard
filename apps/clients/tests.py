from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile


from apps.accounts.models import UserProfile
from apps.billing.models import ServicePackage, SessionPackageTemplate
from apps.clients.models import Client
from apps.practices.models import ExternalIntegration, Practice, TherapistProfile


class ClientModelTests(TestCase):
    
    def setUp(self):
        self.practice = Practice.objects.create(name="Nuvia Wellnes")
        self.user = get_user_model().objects.create_user(username="drSmith")
        self.therapist = TherapistProfile.objects.create(
            user=self.user,
            practice=self.practice,
            license_number="ABC123",
            license_state="CA",
        )
        
    def test_client_string_retun_full_name(self):
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice
        )
        
        self.assertEqual(str(client), "Ana Perez")
        
    def test_public_id_is_created(self):
        """test public id"""
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice,
            primary_therapist=self.therapist,
        )
        
        self.assertIsNotNone(client.public_id)
        
    def test_client_can_have_primary_therapist_from_same_practice(self):
        """can have a client can have therapist from same practice"""
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice,
            primary_therapist=self.therapist,
        )
        
        client.full_clean()

    def test_client_can_exit_without_primary_therapist(self):
        """can have a client can have therapist from same practice"""
        client = Client.objects.create(
            first_name="Ana",
            last_name="Perez",
            practice=self.practice,
        )
        
        client.full_clean()
        
    def test_client_rejects_therapist_from_other_practice(self):
        """verify that the client cannot be assigned 
        a primary therapist from a diferent practice"""
        
        other_practice = Practice.objects.create(name="Other clinic")
        other_user = get_user_model().objects.create_user(
            username="othertherapis"
            )
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="ABC123",
            license_state="NY",
        )
        
        client = Client.objects.create(
            primary_therapist=other_therapist,
            practice=self.practice,
            first_name="Ana",
            last_name="Perez",
        )
        
        with self.assertRaises(ValidationError):
            client.full_clean()


@override_settings(MFA_REQUIRED=False)
class ClientViewTests(TestCase):
    def profile_photo(self):
        buffer = BytesIO()
        Image.new('RGB', (10, 10), 'blue').save(buffer, format='PNG')
        return SimpleUploadedFile('client.png', buffer.getvalue(), content_type='image/png')
    def create_practice_user(self, username="drsmith", practice_name="Nuvia Wellness"):
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
        UserProfile.objects.create(
            user=user,
            practice=practice,
            role=UserProfile.Role.OWNER,
        )
        practice.stripe_connect_account_id = "acct_test"
        practice.stripe_connect_charges_enabled = True
        practice.stripe_connect_payouts_enabled = True
        practice.save(update_fields=["stripe_connect_account_id", "stripe_connect_charges_enabled", "stripe_connect_payouts_enabled"])
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            send_email_enabled=True,
        )
        return user, practice, therapist

    def test_client_list_requires_login(self):
        response = self.client.get(reverse("clients:list"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('clients:list')}")

    def test_client_create_requires_login(self):
        response = self.client.get(reverse("clients:create"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('clients:create')}")

    def test_client_can_be_created_without_email_or_online_payments(self):
        user, _practice, _therapist = self.create_practice_user()
        ExternalIntegration.objects.all().delete()
        Practice.objects.filter(pk=_practice.pk).update(
            stripe_connect_account_id='',
            stripe_connect_charges_enabled=False,
            stripe_connect_payouts_enabled=False,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("clients:create"))

        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('clients:create'), {
            'first_name': 'Maya', 'last_name': 'Johnson', 'status': 'active',
        })
        self.assertRedirects(response, reverse('clients:list'))
        client = Client.objects.get(practice=_practice)
        self.assertEqual(client.first_name, 'Maya')
        self.assertEqual(client.practice, _practice)

    def test_client_list_is_scoped_to_user_practice(self):
        user, practice, _therapist = self.create_practice_user()
        _other_user, other_practice, _other_therapist = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
        SessionPackageTemplate.objects.create(
            practice=practice,
            name="4 prepaid sessions",
            sessions_included=4,
            price=Decimal("520.00"),
        )
        Client.objects.create(practice=other_practice, first_name="Hidden", last_name="Client")

        self.client.force_login(user)
        response = self.client.get(reverse("clients:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My patients")
        self.assertContains(response, "Maya Johnson")
        self.assertContains(response, 'id="client-create-modal"')
        self.assertContains(response, 'data-modal-target="appointment-create-modal"')
        self.assertContains(response, 'id="appointment-create-modal"')
        self.assertContains(response, f'id="client-note-modal-{client.pk}"')
        self.assertContains(response, f'id="client-package-modal-{client.pk}"')
        self.assertContains(response, "Open")
        self.assertContains(response, 'role="region" aria-labelledby="client-directory-heading"')
        self.assertContains(response, 'id="client-directory-scroll-help"')
        self.assertContains(response, '<th scope="col">Client</th>', html=True)
        self.assertContains(response, '<th scope="col">Actions</th>', html=True)
        self.assertContains(response, "Therapist")
        self.assertContains(response, "Insurance")
        self.assertContains(response, "4 prepaid sessions")
        self.assertContains(response, reverse("clients:create"))
        self.assertContains(response, "Create client")
        self.assertContains(response, reverse("clients:edit", args=[client.pk]))
        self.assertContains(response, f'id="client-modal-{client.pk}"')
        self.assertContains(response, "Save changes")
        self.assertContains(response, "Delete client")
        self.assertNotContains(response, "Hidden Client")

    def test_client_detail_is_scoped_and_shows_workspace_sections(self):
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Maya', last_name='Johnson')
        other_user, other_practice, _other_therapist = self.create_practice_user(
            username='otherdoc', practice_name='Other Practice'
        )
        other_client = Client.objects.create(practice=other_practice, first_name='Hidden', last_name='Client')

        self.client.force_login(user)
        response = self.client.get(reverse('clients:detail', args=[client.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Client workspace')
        self.assertContains(response, 'Maya Johnson')
        self.assertContains(response, 'Latest session')
        self.assertNotContains(response, 'Upcoming appointments')
        self.assertNotContains(response, 'Recent appointments')
        self.assertContains(response, 'treatment plans')
        self.assertContains(response, 'Clinical notes')
        self.assertContains(response, reverse('clients:list'))
        self.assertContains(response, 'id="client-edit-modal"')
        self.assertContains(response, 'data-modal-target="client-edit-modal"')
        self.assertEqual(self.client.get(reverse('clients:detail', args=[other_client.pk])).status_code, 404)

    def test_client_chart_denied_sections_do_not_expose_records_or_actions(self):
        from apps.clinical.models import SessionNote
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Read', last_name='Only')
        SessionNote.objects.create(practice=practice, client=client, therapist=therapist, content='Restricted clinical content')
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'clients': {'view': True, 'edit': False}, 'appointments': {'view': False, 'create': False}, 'clinical': {'view': False}, 'billing': {'view': False}, 'documents': {'view': False}, 'requests': {'view': False}}
        profile.save()
        self.client.force_login(user)
        for tab in ['overview', 'clinical', 'billing', 'documents', 'invalid']:
            response = self.client.get(reverse('clients:detail', args=[client.pk]), {'tab': tab})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['workspace_tab'], 'overview')
            self.assertNotContains(response, 'Restricted clinical content')
            self.assertNotContains(response, '?tab=clinical')
            self.assertNotContains(response, '?tab=billing')
            self.assertNotContains(response, '?tab=documents')
            self.assertNotContains(response, 'id="client-edit-modal"')
            self.assertNotIn('notes', response.context)
            self.assertNotIn('invoices', response.context)
            self.assertNotIn('documents', response.context)

    def test_client_chart_billing_balance_includes_partial_payments(self):
        from apps.billing.models import Invoice, Payment
        from django.utils import timezone
        user, practice, _therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Example', last_name='Billing')
        invoice = Invoice.objects.create(practice=practice, client=client, invoice_number='CHART-001', amount=Decimal('125.00'))
        Payment.objects.create(practice=practice, client=client, invoice=invoice, amount=Decimal('30.00'), paid_at=timezone.now())
        Payment.objects.create(practice=practice, client=client, invoice=invoice, amount=Decimal('20.00'), paid_at=timezone.now())
        self.client.force_login(user)
        response = self.client.get(reverse('clients:detail', args=[client.pk]), {'tab': 'billing'})
        self.assertEqual(response.context['invoices'][0].workspace_balance, Decimal('75.00'))
        self.assertContains(response, '$75.00')
        self.assertContains(response, reverse('billing:invoice_print', args=[invoice.pk]))

    def test_therapist_without_client_read_permission_is_forbidden(self):
        user, practice, _therapist = self.create_practice_user()
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'clients': {'view': False}}
        profile.save(update_fields=['role', 'permissions', 'updated_at'])

        self.client.force_login(user)
        response = self.client.get(reverse('clients:list'))

        self.assertRedirects(response, reverse('dashboard'))

    def test_client_page_can_assign_package_to_client(self):
        user, practice, _therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")
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
            "purchased_at": "2026-09-23",
            "expires_at": "",
            "notes": "Assigned from client page.",
        })

        self.assertRedirects(response, reverse("billing:list"))
        package = ServicePackage.objects.get()
        self.assertEqual(package.client, client)
        self.assertEqual(package.template, template)
        self.assertEqual(package.sessions_remaining, 4)

    def test_client_create_saves_to_user_practice(self):
        user, practice, therapist = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.post(reverse("clients:create"), {
            "first_name": "Maya",
            "last_name": "Johnson",
            "profile_photo": self.profile_photo(),
            "email": "maya@example.com",
            "phone": "555-0101",
            "date_of_birth": "1991-04-12",
            "status": Client.Status.ACTIVE,
            "primary_therapist": therapist.pk,
            "insurance_provider": "Aetna",
            "insurance_member_id": "AET123",
            "emergency_contact_name": "Jordan Johnson",
            "emergency_contact_phone": "555-0102",
            "address_line1": "123 Main St",
            "address_line2": "Apt 4",
        })

        self.assertRedirects(response, reverse("clients:list"))
        client = Client.objects.get()
        self.assertEqual(client.practice, practice)
        self.assertEqual(client.primary_therapist, therapist)
        self.assertEqual(client.email, "maya@example.com")
        self.assertTrue(client.profile_photo.name.startswith('client-photos/'))

    def test_client_create_rejects_therapist_from_another_practice(self):
        user, _practice, _therapist = self.create_practice_user()
        _other_user, _other_practice, other_therapist = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )

        self.client.force_login(user)
        response = self.client.post(reverse("clients:create"), {
            "first_name": "Maya",
            "last_name": "Johnson",
            "email": "",
            "phone": "",
            "date_of_birth": "",
            "status": Client.Status.ACTIVE,
            "primary_therapist": other_therapist.pk,
            "insurance_provider": "",
            "insurance_member_id": "",
            "emergency_contact_name": "",
            "emergency_contact_phone": "",
            "address_line1": "",
            "address_line2": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Client.objects.count(), 0)

    def test_client_update_saves_changes(self):
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")

        self.client.force_login(user)
        response = self.client.post(reverse("clients:edit", args=[client.pk]), {
            "first_name": "Maya",
            "last_name": "Rivera",
            "email": "maya.rivera@example.com",
            "phone": "555-0101",
            "date_of_birth": "1991-04-12",
            "status": Client.Status.INACTIVE,
            "primary_therapist": therapist.pk,
            "insurance_provider": "Aetna",
            "insurance_member_id": "AET123",
            "emergency_contact_name": "Jordan Johnson",
            "emergency_contact_phone": "555-0102",
            "address_line1": "123 Main St",
            "address_line2": "Apt 4",
        })

        self.assertRedirects(response, reverse("clients:list"))
        client.refresh_from_db()
        self.assertEqual(client.last_name, "Rivera")
        self.assertEqual(client.status, Client.Status.INACTIVE)
        self.assertEqual(client.primary_therapist, therapist)

    def test_client_update_is_scoped_to_user_practice(self):
        user, _practice, _therapist = self.create_practice_user()
        _other_user, other_practice, _other_therapist = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        client = Client.objects.create(practice=other_practice, first_name="Hidden", last_name="Client")

        self.client.force_login(user)
        response = self.client.get(reverse("clients:edit", args=[client.pk]))

        self.assertEqual(response.status_code, 404)

    def test_client_edit_form_shows_delete_action(self):
        user, practice, _therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")

        self.client.force_login(user)
        response = self.client.get(reverse("clients:edit", args=[client.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete client")
        self.assertContains(response, reverse("clients:delete", args=[client.pk]))

    def test_client_delete_removes_client(self):
        user, practice, _therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name="Maya", last_name="Johnson")

        self.client.force_login(user)
        response = self.client.post(reverse("clients:delete", args=[client.pk]))

        self.assertRedirects(response, reverse("clients:list"))
        self.assertEqual(Client.objects.count(), 0)

    def test_client_delete_is_scoped_to_user_practice(self):
        user, _practice, _therapist = self.create_practice_user()
        _other_user, other_practice, _other_therapist = self.create_practice_user(
            username="otherdoc",
            practice_name="Other Practice",
        )
        client = Client.objects.create(practice=other_practice, first_name="Hidden", last_name="Client")

        self.client.force_login(user)
        response = self.client.post(reverse("clients:delete", args=[client.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Client.objects.count(), 1)
