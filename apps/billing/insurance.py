"""Practice-local payer selection and explicit, non-binding rate suggestions."""
from django.db.models import Q
from .models import InsurancePayer, InsuranceRate


def available_payers(practice):
    if not practice:
        return InsurancePayer.objects.none()
    return InsurancePayer.objects.filter(active=True).filter(
        Q(practice=practice) | Q(practice__isnull=True, practice_selections__practice=practice,
                                practice_selections__active=True)).distinct().order_by('name')


def rate_suggestion(practice, client, state, service_code):
    if not client or client.practice_id != practice.pk or client.billing_type != 'insurance' or not client.insurance_payer_id:
        return None
    if not available_payers(practice).filter(pk=client.insurance_payer_id).exists():
        return None
    return InsuranceRate.objects.filter(practice=practice, payer_id=client.insurance_payer_id,
        state=state.upper(), service_code=service_code, active=True, reimbursement_amount__isnull=False).first()
