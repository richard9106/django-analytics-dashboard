"""Versioned preview and subscription terms; not clinical launch approval."""
TERMS_VERSION = '2026-10-20-standard-v4'
BILLING_TERMS_VERSION = '2026-10-15-commercial-v2'
PRIVACY_VERSION = '2026-10-20-v3'


def legal_context(request):
    from django.conf import settings
    return {'terms_version': TERMS_VERSION, 'privacy_version': PRIVACY_VERSION, 'billing_terms_version': BILLING_TERMS_VERSION,
            'operator_tax_id': settings.OPERATOR_TAX_ID,
            'stripe_live': settings.STRIPE_SECRET_KEY.startswith(('sk_live_', 'rk_live_'))}
