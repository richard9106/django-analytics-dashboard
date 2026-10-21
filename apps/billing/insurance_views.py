from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from apps.accounts.access import PracticePermissionMixin
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.clients.models import Client
from .views import PracticeContextMixin
from .models import InsurancePayer, PracticeInsurancePayer
from .insurance import rate_suggestion, available_payers


class PracticePayerToggleView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'billing'
    permission_action = 'edit'

    @transaction.atomic
    def post(self, request, pk):
        practice = self.get_practice()
        if not practice or request.POST.get('active') not in ('0', '1'):
            return HttpResponseBadRequest('Choose enable or disable.')
        payer = get_object_or_404(InsurancePayer, pk=pk, practice__isnull=True, active=True)
        # A practice lock serializes repeated enable/disable requests.
        type(practice).objects.select_for_update().get(pk=practice.pk)
        active = request.POST['active'] == '1'
        PracticeInsurancePayer.objects.update_or_create(practice=practice, payer=payer, defaults={'active': active})
        log_audit_event(request, AuditLog.Action.UPDATE, 'billing.PracticeInsurancePayer', payer.pk,
                        practice=practice, metadata={'active': active})
        messages.success(request, 'Payer enabled for your practice.' if active else 'Payer disabled. Existing client and invoice records are retained.')
        return redirect('settings:insurance')


class InsuranceRateSuggestionView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'billing'
    permission_action = 'view'

    def get(self, request):
        practice = self.get_practice()
        value = request.GET.get('client', '')
        if not value.isascii() or not value.isdigit() or len(value) > 18:
            return HttpResponseBadRequest('Select a client.')
        client = get_object_or_404(Client.objects.select_related('insurance_payer'), pk=value, practice=practice)
        state = request.GET.get('state') or client.insurance_state
        service = request.GET.get('service_code', '')
        enabled = bool(client.insurance_payer_id and available_payers(practice).filter(pk=client.insurance_payer_id).exists())
        rate = rate_suggestion(practice, client, state, service)
        response = JsonResponse({'billing_type': client.billing_type, 'payer_enabled': enabled,
            'payer_name': client.insurance_payer.name if enabled else '', 'state': state.upper(),
            'amount': str(rate.reimbursement_amount) if rate else None,
            'client_share': str(client.insurance_copay) if client.insurance_copay is not None else None,
            'message': 'Contracted reference only. Confirm the charge and client share; this does not verify coverage.' if rate else 'No active matching rate. Enter the charge and confirm the client share manually.'})
        response['Cache-Control'] = 'private, no-store'
        return response
