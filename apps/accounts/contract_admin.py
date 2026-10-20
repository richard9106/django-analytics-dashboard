from django.contrib import admin
from django.db import transaction

from apps.audit.models import AuditLog
from .contract_forms import PublishContractBundleForm
from .contract_models import ClinicalContractRequest, ClinicalContractBundle, ClinicalContractSignature, StandardAgreementAcceptance


class ContractEvidenceAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(ClinicalContractRequest)
class ContractRequestAdmin(ContractEvidenceAdmin):
    list_display = ('practice', 'requested_by', 'created_at')
    readonly_fields = ('practice', 'requested_by', 'details', 'created_at')
    search_fields = ('practice__name',)


@admin.register(ClinicalContractSignature)
class ContractSignatureAdmin(ContractEvidenceAdmin):
    list_display = ('bundle', 'signer_name', 'created_at')
    readonly_fields = ('bundle', 'signer', 'signer_name', 'signer_email', 'signer_title',
                       'bundle_digest', 'consent_text', 'created_at')


@admin.register(ClinicalContractBundle)
class ContractBundleAdmin(ContractEvidenceAdmin):
    form = PublishContractBundleForm
    list_display = ('request', 'version', 'provider_name', 'created_at')
    readonly_fields = ('provider_signer', 'provider_consent', 'digest', 'created_at')

    def has_add_permission(self, request):
        # Publishing binds NuviaMy; practice administrators cannot act as the provider.
        return request.user.is_active and request.user.is_superuser

    def get_fields(self, request, obj=None):
        fields = ['request', 'version', 'dpa_text', 'baa_text', 'schedule_text', 'provider_name', 'provider_title']
        return fields + (['provider_signer', 'provider_consent', 'digest', 'created_at'] if obj else ['execute_as_provider'])

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        from apps.practices.models import Practice
        Practice.objects.select_for_update().get(pk=obj.request.practice_id)
        obj.provider_signer = request.user
        obj.save()
        AuditLog.objects.create(practice=obj.request.practice, actor=request.user,
            action=AuditLog.Action.CREATE, object_type='clinical_contract', object_id=str(obj.pk),
            metadata={'event': 'contract_provider_signed', 'digest': obj.digest})


@admin.register(StandardAgreementAcceptance)
class StandardAgreementAcceptanceAdmin(ContractEvidenceAdmin):
    list_display = ('practice', 'signer', 'version', 'created_at')
    readonly_fields = ('practice', 'signer', 'version', 'snapshot', 'digest', 'created_at')
    search_fields = ('practice__name', 'signer__email')
