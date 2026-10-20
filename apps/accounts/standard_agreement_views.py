import io
import json
from zipfile import ZipFile, ZIP_DEFLATED

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from .contract_models import StandardAgreementAcceptance
from .contract_views import ContractOwnerMixin
from .standard_agreements import documents, AGREEMENT_VERSION
from apps.audit.models import AuditLog


class StandardAgreementOfferView(View):
    def get(self, request):
        sections = []
        for name, text in documents().items():
            if name in ('terms', 'privacy'):
                continue
            blocks = text.strip().split('\n\n')
            sections.append({'name': name, 'title': blocks[0].lstrip('# '),
                             'blocks': [{'heading': block.startswith('## '),
                                         'text': block.lstrip('# ') if block.startswith('## ') else block}
                                        for block in blocks[1:]]})
        return render(request, 'accounts/standard_agreement_offer.html',
                      {'sections': sections, 'agreement_version': AGREEMENT_VERSION})


class StandardAgreementDownloadView(ContractOwnerMixin, View):
    def get(self, request, pk):
        acceptance = get_object_or_404(StandardAgreementAcceptance, pk=pk, practice=self.practice)
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('acceptance.json', json.dumps({
                'snapshot': acceptance.snapshot, 'sha256': acceptance.digest,
                'accepted_at': acceptance.created_at.isoformat()}, ensure_ascii=False, indent=2))
            for name, text in acceptance.snapshot['documents'].items():
                extension = 'html' if name in ('terms', 'privacy') else 'txt'
                archive.writestr(f'{name}.{extension}', text)
        AuditLog.objects.create(practice=self.practice, actor=request.user, action=AuditLog.Action.EXPORT,
            object_type='service_agreement', object_id=str(acceptance.pk),
            metadata={'event': 'standard_agreements_downloaded', 'agreement_digest': acceptance.digest})
        response = HttpResponse(output.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="nuviamy-agreements-{acceptance.pk}.zip"'
        response['Cache-Control'] = 'private, no-store'
        return response
