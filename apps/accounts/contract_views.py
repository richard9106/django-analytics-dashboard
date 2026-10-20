import io
import json
from zipfile import ZipFile, ZIP_DEFLATED

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.audit.models import AuditLog
from apps.rate_limit import PostRateLimitMixin
from .models import UserProfile
from .contract_models import ClinicalContractRequest, ClinicalContractBundle, ClinicalContractSignature
from .contract_forms import ContractRequestForm, ContractSignatureForm, SIGNING_CONSENT


class ContractOwnerMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = getattr(request.user, 'nuvia_profile', None)
            if not profile or profile.role != UserProfile.Role.OWNER or not request.user.is_active:
                request._audit_denied_reason = 'contract_owner_required'
                return HttpResponseForbidden('Only the practice owner can manage clinical contracts.')
            self.practice = profile.practice
        return super().dispatch(request, *args, **kwargs)


def contract_event(request, practice, event, object_id):
    AuditLog.objects.create(practice=practice, actor=request.user, action=AuditLog.Action.CREATE,
        object_type='clinical_contract', object_id=str(object_id), metadata={'event': event})


class ContractsView(ContractOwnerMixin, PostRateLimitMixin, View):
    rate_limit_scope = 'contract_request'
    rate_limit_count = 10
    rate_limit_seconds = 900

    def get(self, request):
        return self.show(request)

    def show(self, request, form=None):
        submission = ClinicalContractRequest.objects.filter(practice=self.practice).order_by('-created_at', '-pk').first()
        bundles = ClinicalContractBundle.objects.filter(request__practice=self.practice).select_related('customer_signature')
        revising = bool(submission and (request.GET.get('revise') == '1' or form is not None))
        initial = dict(submission.details) if revising else {
            'legal_name': self.practice.name, 'representative_name': request.user.get_full_name(),
            'privacy_email': request.user.email}
        initial['authority'] = False
        return render(request, 'accounts/contracts.html', {
            'submission': submission, 'bundles': bundles, 'show_form': not submission or revising,
            'has_current_bundle': bool(submission and submission.bundles.exists()),
            'request_revision': str(submission.pk) if submission else '',
            'form': form or ContractRequestForm(initial=initial),
        })

    @transaction.atomic
    def post(self, request):
        # Lock the practice to serialize duplicate submissions, including the first request.
        from apps.practices.models import Practice
        Practice.objects.select_for_update().get(pk=self.practice.pk)
        previous = ClinicalContractRequest.objects.filter(practice=self.practice).order_by('-created_at', '-pk').first()
        if previous and request.POST.get('request_revision') != str(previous.pk):
            return redirect('clinical_contracts')
        form = ContractRequestForm(request.POST)
        if not form.is_valid():
            return self.show(request, form)
        if not request.user.email:
            form.add_error(None, 'Add a deliverable account email in Profile settings before requesting agreements.')
            return self.show(request, form)
        submission = ClinicalContractRequest.objects.create(practice=self.practice,
            requested_by=request.user, details=form.cleaned_data)
        contract_event(request, self.practice, 'contract_requested', submission.pk)
        messages.success(request, 'Your practice details have been submitted. NuviaMy will prepare your contract packet for review.')
        return redirect('clinical_contracts')


class ContractReviewView(ContractOwnerMixin, View):
    def get(self, request, pk):
        bundle = get_object_or_404(ClinicalContractBundle.objects.select_related('request', 'customer_signature'),
                                  pk=pk, request__practice=self.practice)
        # Only a server-rendered, tenant-scoped review grants a short signing window.
        request.session['contract_review'] = {'bundle': str(bundle.pk), 'digest': bundle.digest,
                                              'at': timezone.now().timestamp()}
        return render(request, 'accounts/contract_review.html', {
            'bundle': bundle, 'is_latest': (bundle.request.bundles.first().pk == bundle.pk and
                          ClinicalContractRequest.objects.filter(practice=self.practice).order_by('-created_at', '-pk').first().pk == bundle.request_id),
            'form': ContractSignatureForm(initial={
                'bundle_digest': bundle.digest, 'signer_name': bundle.request.details['representative_name']}),
        })


class ContractSignView(ContractOwnerMixin, PostRateLimitMixin, View):
    rate_limit_scope = 'contract_sign'
    rate_limit_count = 10
    rate_limit_seconds = 900

    @transaction.atomic
    def post(self, request, pk):
        # The same practice lock serializes requests, publication and customer signature.
        from apps.practices.models import Practice
        Practice.objects.select_for_update().get(pk=self.practice.pk)
        bundle = get_object_or_404(ClinicalContractBundle.objects.select_related('request'), pk=pk, request__practice=self.practice)
        submission = bundle.request
        if ClinicalContractSignature.objects.filter(bundle=bundle).exists():
            return redirect('clinical_contract_review', pk=pk)
        review = request.session.get('contract_review', {})
        form = ContractSignatureForm(request.POST)
        latest = submission.bundles.first()
        valid_review = (review.get('bundle') == str(pk) and review.get('digest') == bundle.digest
                        and 0 <= timezone.now().timestamp() - review.get('at', 0) < 1800)
        latest_request = ClinicalContractRequest.objects.filter(practice=self.practice).order_by('-created_at', '-pk').first()
        if not valid_review or not latest or latest.pk != bundle.pk or latest_request.pk != submission.pk:
            messages.error(request, 'Review the latest complete contract packet before signing.')
            return redirect('clinical_contracts')
        if form.is_valid():
            if not request.user.email:
                form.add_error(None, 'Add a deliverable account email in Profile settings before signing.')
            if form.cleaned_data['bundle_digest'] != bundle.digest:
                form.add_error(None, 'The contract changed. Review the complete packet again.')
            if form.cleaned_data['signer_name'].strip().casefold() != submission.details['representative_name'].strip().casefold():
                form.add_error('signer_name', 'Use the authorized representative name supplied for this practice.')
        if not form.is_valid():
            return render(request, 'accounts/contract_review.html', {'bundle': bundle, 'form': form, 'is_latest': True})
        signature = ClinicalContractSignature.objects.create(bundle=bundle, signer=request.user,
            signer_name=form.cleaned_data['signer_name'], signer_email=request.user.email,
            signer_title=submission.details['representative_title'], bundle_digest=bundle.digest, consent_text=SIGNING_CONSENT)
        contract_event(request, self.practice, 'contract_customer_signed', signature.pk)
        request.session.pop('contract_review', None)
        messages.success(request, 'Your signature has been recorded. Download your copy below. Clinical use remains pending separate approval.')
        return redirect('clinical_contract_review', pk=pk)


class ContractDownloadView(ContractOwnerMixin, View):
    def get(self, request, pk):
        bundle = get_object_or_404(ClinicalContractBundle.objects.select_related('request', 'customer_signature'),
                                  pk=pk, request__practice=self.practice)
        payload = bundle.payload()
        signature = getattr(bundle, 'customer_signature', None)
        receipt = {'bundle_digest_sha256': bundle.digest, 'provider_signature': payload['provider'],
                   'clinical_approval': 'not_granted_by_contract_signature', 'customer_signature': None}
        if signature:
            receipt['customer_signature'] = {
                'user_id': signature.signer_id, 'name': signature.signer_name, 'email': signature.signer_email,
                'title': signature.signer_title, 'signed_at': signature.created_at.isoformat(),
                'consent': signature.consent_text, 'bundle_digest_sha256': signature.bundle_digest,
            }
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('contract-packet.json', json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
            archive.writestr('signature-receipt.json', json.dumps(receipt, ensure_ascii=False, indent=2))
            for name, text in payload['documents'].items():
                if text:
                    archive.writestr(f'{name}.txt', text)
        AuditLog.objects.create(practice=self.practice, actor=request.user, action=AuditLog.Action.EXPORT,
            object_type='clinical_contract', object_id=str(bundle.pk), metadata={'event': 'contract_downloaded'})
        response = HttpResponse(output.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="nuviamy-contract-{bundle.pk}.zip"'
        response['Cache-Control'] = 'private, no-store'
        return response
