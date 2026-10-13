"""Versioned professional-preview notices; not clinical launch approval."""
TERMS_VERSION = '2026-10-13-preview-v1'
PRIVACY_VERSION = '2026-10-13-v1'


def legal_context(request):
    from django.conf import settings
    return {'terms_version': TERMS_VERSION, 'privacy_version': PRIVACY_VERSION,
            'operator_tax_id': settings.OPERATOR_TAX_ID}
