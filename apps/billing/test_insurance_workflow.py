from decimal import Decimal
from unittest.mock import patch
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.practices.models import Practice
from apps.clients.models import Client
from apps.clients.forms import ClientForm
from apps.accounts.models import UserProfile
from apps.accounts.export import build_export_data
from .models import InsurancePayer, InsuranceRate, PracticeInsurancePayer, Invoice, Payment
from .forms import InvoiceForm, InsuranceRateForm, PaymentForm
from .insurance import available_payers


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False)
class InsuranceWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.practice = Practice.objects.create(name='Insurance practice')
        cls.other = Practice.objects.create(name='Other practice')
        cls.user = get_user_model().objects.create_user('insurance-owner', email='owner@example.invalid')
        UserProfile.objects.create(user=cls.user, practice=cls.practice, role='owner')
        cls.payer = InsurancePayer.objects.create(name='Test catalogue insurer', is_system_template=True)
        PracticeInsurancePayer.objects.create(practice=cls.practice, payer=cls.payer)
        cls.client_record = Client.objects.create(practice=cls.practice, first_name='Test', last_name='Client', billing_type='insurance', insurance_payer=cls.payer, insurance_state='CA', insurance_copay='20')
        cls.rate = InsuranceRate.objects.create(practice=cls.practice, payer=cls.payer, state='CA', service_code='90837', reimbursement_amount='120')

    def setUp(self):
        self.client.force_login(self.user)

    def invoice_data(self, **extra):
        return dict(client=self.client_record.pk, invoice_number='INS-001', billing_type='insurance',
                    service_code='90837', insurance_state='CA', client_responsibility='20', amount='120', status='draft') | extra

    def invoice(self):
        form = InvoiceForm(self.invoice_data(), practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_payer_selection_is_local_non_destructive_and_idempotent(self):
        path = reverse('settings:insurance_payer_selection', args=[self.payer.pk])
        self.assertEqual(self.client.get(path).status_code, 405)
        for _ in range(2):
            self.assertEqual(self.client.post(path, {'active': '0'}).status_code, 302)
        self.assertFalse(available_payers(self.practice).filter(pk=self.payer.pk).exists())
        self.assertEqual(InsuranceRate.objects.get().pk, self.rate.pk)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.insurance_payer_id, self.payer.pk)
        self.payer.refresh_from_db()
        self.assertTrue(self.payer.active)
        self.assertEqual(PracticeInsurancePayer.objects.filter(practice=self.practice).count(), 1)
        self.assertFalse(PracticeInsurancePayer.objects.filter(practice=self.other).exists())
        self.assertEqual(self.client.post(path, {'active': '1'}).status_code, 302)
        self.assertTrue(available_payers(self.practice).filter(pk=self.payer.pk).exists())

    def test_selection_denies_other_custom_payers_and_view_only_roles(self):
        other_payer = InsurancePayer.objects.create(practice=self.other, name='Hidden insurer')
        self.assertEqual(self.client.post(reverse('settings:insurance_payer_selection', args=[other_payer.pk]), {'active': '1'}).status_code, 404)
        profile = self.user.nuvia_profile
        profile.role = 'therapist'
        profile.permissions = {'billing': {'view': True}}
        profile.save()
        response = self.client.post(reverse('settings:insurance_payer_selection', args=[self.payer.pk]), {'active': '0'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PracticeInsurancePayer.objects.get().active)

    def test_new_rates_require_enabled_payer(self):
        PracticeInsurancePayer.objects.filter(practice=self.practice).update(active=False)
        form = InsuranceRateForm(dict(payer=self.payer.pk, state='NY', service_code='90834', reimbursement_amount='50', active=True), practice=self.practice)
        self.assertFalse(form.is_valid())
        self.assertIn('payer', form.errors)

    def test_quote_is_scoped_and_excludes_inactive_rates_and_payers(self):
        path = reverse('billing:insurance_rate_suggestion')
        params = {'client': self.client_record.pk, 'service_code': '90837'}
        data = self.client.get(path, params).json()
        self.assertEqual(data['amount'], '120.00')
        self.assertEqual(data['client_share'], '20.00')
        stranger = Client.objects.create(practice=self.other, first_name='Other', last_name='Client')
        self.assertEqual(self.client.get(path, params | {'client': stranger.pk}).status_code, 404)
        self.assertEqual(self.client.get(path, params | {'state': 'NY'}).json()['amount'], None)
        InsuranceRate.objects.filter(pk=self.rate.pk).update(active=False)
        self.assertIsNone(self.client.get(path, params).json()['amount'])
        PracticeInsurancePayer.objects.filter(practice=self.practice).update(active=False)
        self.assertFalse(self.client.get(path, params).json()['payer_enabled'])

    def test_client_form_links_payer_and_keeps_legacy_reference_without_fuzzy_linking(self):
        data = dict(first_name='Linked', last_name='Client', status='active', billing_type='insurance', insurance_payer=self.payer.pk, insurance_state='ca', insurance_copay='20')
        form = ClientForm(data, practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors)
        linked = form.save()
        self.assertEqual(linked.insurance_provider, self.payer.name)
        self.assertEqual(linked.insurance_state, 'CA')
        form = ClientForm(data | {'insurance_payer': ''}, practice=self.practice)
        self.assertFalse(form.is_valid())
        hidden = InsurancePayer.objects.create(practice=self.other, name='Hidden')
        form = ClientForm(data | {'insurance_payer': hidden.pk}, practice=self.practice)
        self.assertFalse(form.is_valid())
        legacy = Client.objects.create(practice=self.practice, first_name='Legacy', last_name='Client', insurance_provider='Test catalogue insurer')
        self.assertIsNone(legacy.insurance_payer_id)
        self.assertEqual(legacy.billing_type, 'self_pay')

    def test_client_form_can_retain_disabled_historical_payer(self):
        PracticeInsurancePayer.objects.filter(practice=self.practice).update(active=False)
        form = ClientForm(dict(first_name='Test', last_name='Client', status='active', billing_type='insurance', insurance_payer=self.payer.pk), instance=self.client_record, practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().insurance_payer_id, self.payer.pk)
        form = ClientForm(dict(first_name='New', last_name='Client', status='active', billing_type='insurance', insurance_payer=self.payer.pk), practice=self.practice)
        self.assertFalse(form.is_valid())

    def test_invoice_snapshot_preserves_rate_and_payer_when_catalogue_changes(self):
        invoice = self.invoice()
        self.assertEqual(invoice.insurance_responsibility, Decimal('100'))
        self.assertEqual(invoice.client_balance_due, Decimal('20'))
        self.assertEqual(invoice.contracted_amount, Decimal('120'))
        InsuranceRate.objects.filter(pk=self.rate.pk).update(reimbursement_amount=Decimal('180'))
        InsurancePayer.objects.filter(pk=self.payer.pk).update(name='Renamed')
        PracticeInsurancePayer.objects.filter(practice=self.practice).update(active=False)
        form = InvoiceForm(self.invoice_data(notes='Note correction'), instance=invoice, practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertEqual(updated.contracted_amount, Decimal('120'))
        self.assertEqual(updated.insurance_payer_name, 'Test catalogue insurer')
        self.assertEqual(updated.amount, Decimal('120'))

    def test_invoice_requires_explicit_share_and_never_auto_uses_a_reference_rate(self):
        for extra in ({'client_responsibility': ''}, {'client_responsibility': '121'}, {'amount': ''}, {'insurance_state': ''}, {'service_code': ''}):
            form = InvoiceForm(self.invoice_data(**extra), practice=self.practice)
            self.assertFalse(form.is_valid(), extra)
        form = InvoiceForm(self.invoice_data(amount='110'), practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().amount, Decimal('110'))

    def test_manual_payments_have_separate_caps_and_settle_only_after_both_parts(self):
        invoice = self.invoice()
        for method, amount in [('card', '21'), ('insurance', '101')]:
            form = PaymentForm(dict(invoice=invoice.pk, amount=amount, method=method, paid_at=timezone.now().strftime('%Y-%m-%dT%H:%M')), practice=self.practice)
            self.assertFalse(form.is_valid())
        for method, amount, paid in [('card', '20', False), ('insurance', '100', True)]:
            response = self.client.post(reverse('billing:payment_create'), dict(invoice=invoice.pk, amount=amount, method=method, paid_at=timezone.now().strftime('%Y-%m-%dT%H:%M')))
            self.assertEqual(response.status_code, 302)
            invoice.refresh_from_db()
            self.assertEqual(invoice.status == 'paid', paid)
        self.assertEqual(invoice.client_balance_due, 0)
        self.assertEqual(invoice.insurance_balance_due, 0)

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_local_test')
    @patch('apps.billing.views.stripe.Webhook.construct_event')
    def test_client_stripe_payment_does_not_mark_insurance_share_paid_and_is_idempotent(self, event):
        invoice = self.invoice()
        event.return_value = {'type': 'checkout.session.completed', 'data': {'object': {
            'id': 'cs_insurance_test', 'payment_intent': 'pi_insurance_test', 'payment_status': 'paid', 'currency': 'usd', 'amount_total': 2000,
            'metadata': {'invoice_id': str(invoice.pk), 'practice_id': str(self.practice.pk), 'client_id': str(self.client_record.pk)}}}}
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('billing:stripe_webhook'), '{}', content_type='application/json').status_code, 200)
        invoice.refresh_from_db()
        self.assertNotEqual(invoice.status, 'paid')
        self.assertEqual(invoice.client_balance_due, 0)
        self.assertEqual(invoice.insurance_balance_due, Decimal('100'))
        self.assertEqual(Payment.objects.filter(invoice=invoice).count(), 1)

    def test_migration_preserves_used_catalogue_payers_only(self):
        PracticeInsurancePayer.objects.all().delete()
        unused = InsurancePayer.objects.create(name='Unused template', is_system_template=True)
        migration = import_module('apps.billing.migrations.0014_preserve_existing_payer_selections')
        migration.preserve(apps, None)
        migration.preserve(apps, None)
        self.assertTrue(available_payers(self.practice).filter(pk=self.payer.pk).exists())
        self.assertFalse(available_payers(self.practice).filter(pk=unused.pk).exists())
        self.assertFalse(available_payers(self.other).exists())

    def test_export_contains_linked_payers_and_frozen_invoice_allocation(self):
        invoice = self.invoice()
        export = build_export_data(self.practice, 'all')
        self.assertEqual(export['invoices'][0]['insurance_payer_name'], invoice.insurance_payer_name)
        self.assertEqual(export['clients'][0]['insurance_payer_id'], self.payer.pk)
        self.assertEqual(export['insurance_rates'][0]['payer_id'], self.payer.pk)
        self.assertEqual(export['payer_selections'][0]['active'], True)

    @override_settings(STRIPE_SECRET_KEY='test-placeholder')
    @patch('apps.portal.views.stripe.checkout.Session.create')
    def test_portal_collects_only_client_share_and_blocks_repeat_collection(self, checkout):
        from types import SimpleNamespace
        from apps.portal.models import ClientPortalAccess
        invoice = self.invoice()
        invoice.status = 'sent'
        invoice.save(update_fields=['status'])
        self.practice.stripe_connect_account_id = 'acct_test_insurance'
        self.practice.stripe_connect_charges_enabled = True
        self.practice.stripe_connect_payouts_enabled = True
        self.practice.save()
        user = get_user_model().objects.create_user('insured-portal-client')
        ClientPortalAccess.objects.create(user=user, practice=self.practice, client=self.client_record, is_active=True)
        self.client.force_login(user)
        checkout.return_value = SimpleNamespace(url='https://checkout.stripe.test/client-share')
        self.assertEqual(self.client.post(reverse('portal:invoice_pay', args=[invoice.pk])).url, checkout.return_value.url)
        self.assertEqual(checkout.call_args.kwargs['line_items'][0]['price_data']['unit_amount'], 2000)
        Payment.objects.create(practice=self.practice, client=self.client_record, invoice=invoice, method='card', amount=20, paid_at=timezone.now())
        checkout.reset_mock()
        self.client.post(reverse('portal:invoice_pay', args=[invoice.pk]))
        checkout.assert_not_called()
        response = self.client.get(reverse('portal:dashboard'))
        self.assertEqual(response.context['open_invoice_total'], 0)

    def test_missing_or_disabled_payer_returns_form_errors_without_server_error(self):
        PracticeInsurancePayer.objects.filter(practice=self.practice).update(active=False)
        form = InvoiceForm(self.invoice_data(), practice=self.practice)
        self.assertFalse(form.is_valid())
        self.assertIn('client', form.errors)
        self.client_record.insurance_payer = None
        self.client_record.save(update_fields=['insurance_payer'])
        form = InvoiceForm(self.invoice_data(), practice=self.practice)
        self.assertFalse(form.is_valid())
        self.assertIn('client', form.errors)

    def test_payer_changes_require_csrf(self):
        from django.test import Client as BrowserClient
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(self.user)
        response = browser.post(reverse('settings:insurance_payer_selection', args=[self.payer.pk]), {'active': '0'})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(PracticeInsurancePayer.objects.get().active)

    def test_configuration_and_client_edit_surfaces_render_the_linked_workflow(self):
        for route in ('settings:insurance', 'clients:list', 'billing:list'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        self.assertContains(self.client.get(reverse('settings:insurance')), 'Available payer catalogue')
        detail = self.client.get(reverse('clients:detail', args=[self.client_record.pk]))
        self.assertContains(detail, 'name="insurance_payer"')
        invoice = self.client.get(reverse('billing:invoice_create'))
        self.assertContains(invoice, 'Load client insurance suggestion')
        self.assertContains(invoice, 'name="client_responsibility"')
