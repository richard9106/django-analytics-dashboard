from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user, must_change_password
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .forms import ClientDocumentForm
from .models import ClientDocument


class PracticeContextMixin:
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['practice'] = practice
        context['document_clients'] = practice.clients.all() if practice else []
        return context


class DocumentListView(LoginRequiredMixin, ClientPortalRedirectMixin, PracticeContextMixin, ListView):
    model = ClientDocument
    template_name = 'documents/list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientDocument.objects.none()
        return ClientDocument.objects.filter(practice=practice).select_related('client', 'uploaded_by')


class DocumentCreateView(LoginRequiredMixin, ClientPortalRedirectMixin, PracticeContextMixin, CreateView):
    model = ClientDocument
    form_class = ClientDocumentForm
    template_name = 'documents/form.html'
    success_url = reverse_lazy('documents:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        kwargs['uploaded_by'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            'documents.ClientDocument',
            self.object.pk,
            practice=self.object.practice,
            metadata={'client_id': self.object.client_id, 'filename': self.object.original_filename},
        )
        return response


class DocumentDeleteView(LoginRequiredMixin, ClientPortalRedirectMixin, PracticeContextMixin, DeleteView):
    model = ClientDocument
    success_url = reverse_lazy('documents:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientDocument.objects.none()
        return ClientDocument.objects.filter(practice=practice)

    def form_valid(self, form):
        storage = self.object.file.storage
        name = self.object.file.name
        document_id = self.object.pk
        practice = self.object.practice
        metadata = {'client_id': self.object.client_id, 'filename': self.object.original_filename}
        response = super().form_valid(form)
        if name:
            storage.delete(name)
        log_audit_event(
            self.request,
            AuditLog.Action.DELETE,
            'documents.ClientDocument',
            document_id,
            practice=practice,
            metadata=metadata,
        )
        return response


class DocumentDownloadView(LoginRequiredMixin, PracticeContextMixin, View):
    def get(self, request, pk):
        if must_change_password(request.user):
            return redirect('force_password_change')
        practice = self.get_practice()
        portal_access = getattr(request.user, 'client_portal_access', None)
        if portal_access and portal_access.is_active:
            document = get_object_or_404(
                ClientDocument,
                pk=pk,
                practice=portal_access.practice,
                client=portal_access.client,
                visible_to_client=True,
            )
        elif practice:
            document = get_object_or_404(ClientDocument, pk=pk, practice=practice)
        else:
            raise PermissionDenied('You do not have access to this document.')
        log_audit_event(
            request,
            AuditLog.Action.EXPORT,
            'documents.ClientDocument',
            document.pk,
            practice=document.practice,
            metadata={'client_id': document.client_id, 'filename': document.original_filename},
        )
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.original_filename or document.file.name.rsplit('/', 1)[-1],
            content_type=document.content_type or 'application/octet-stream',
        )
