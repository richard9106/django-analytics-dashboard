from apps.accounts.standard_agreements import offer_digest
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.audit.models import AuditLog
from apps.practices.models import Practice
from apps.accounts.legal import TERMS_VERSION, PRIVACY_VERSION

@override_settings(MFA_REQUIRED=False)
class LegalAcceptanceTests(TestCase):
    def payload(self, **extra):
        data=dict(accept_terms=True, legal_name='Test legal practice', registered_address='Test street, CA, USA', representative_title='Owner', agreement_digest=offer_digest(), practice_name='Fictional legal test',practice_type='solo',first_name='Fictional',last_name='Owner',email='legal@example.invalid',password1='FictionalLegal2026!',password2='FictionalLegal2026!',license_number='fictional-legal',license_state='CA')
        data.update(extra)
        return data

    def test_unchecked_terms_do_not_create_workspace(self):
        response=self.client.post(reverse('signup'),self.payload(accept_terms=False))
        self.assertEqual(response.status_code,200)
        self.assertIn('accept_terms',response.context['form'].errors)
        self.assertFalse(Practice.objects.exists())

    def test_acceptance_captures_actor_and_versions_once(self):
        response=self.client.post(reverse('signup'),self.payload())
        self.assertEqual(response.status_code,302)
        practice=Practice.objects.get()
        event=AuditLog.objects.get(practice=practice,object_type='service_agreement')
        self.assertEqual(event.actor_id_snapshot,practice.therapists.get().user_id)
        self.assertEqual(event.metadata['terms_version'],TERMS_VERSION)
        self.assertEqual(event.metadata['privacy_notice_version'],PRIVACY_VERSION)
        self.assertContains(self.client.get(reverse('terms_of_service')),'Real client records')

    @override_settings(OPERATOR_TAX_ID='FICTIONAL-TAX-ID')
    def test_public_notices_and_footer_links(self):
        for name in ('legal_notice','terms_of_service','privacy_policy'):
            response=self.client.get(reverse(name))
            self.assertContains(response,'Richard Andres Marles Bonilla')
            self.assertContains(response,'marleswebinfo@gmail.com')
            self.assertContains(response,reverse('terms_of_service'))
            self.assertContains(response,reverse('legal_notice'))
        self.assertContains(self.client.get(reverse('legal_notice')),'FICTIONAL-TAX-ID')
        self.assertNotContains(self.client.get(reverse('legal_notice')),'pending completion')

    def test_commercial_terms_publish_agreed_conditions_and_preview_limits(self):
        from apps.accounts.legal import BILLING_TERMS_VERSION
        response=self.client.get(reverse('terms_of_service'))
        for text in ('subscription-conditions','USD 39','USD 421','paid in advance','renews automatically','00:00 UTC','refund requests','test mode',BILLING_TERMS_VERSION):
            self.assertContains(response,text)


@override_settings(STRIPE_SECRET_KEY='sk_live_fictional')
class LiveCommercialNoticeTests(TestCase):
    def test_terms_explain_real_payments_and_retain_clinical_limit(self):
        response = self.client.get(reverse('terms_of_service'))
        self.assertContains(response, 'authorizes real recurring payments')
        self.assertContains(response, 'prices exclude any applicable taxes')
        self.assertContains(response, 'Real client records')
        self.assertNotContains(response, 'Stripe is in test mode')
