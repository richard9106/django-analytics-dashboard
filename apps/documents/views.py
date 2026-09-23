from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView

from .forms import ClientDocumentForm
from .models import ClientDocument


class PracticeContextMixin:
    def get_practice(self):
        user = self.request.user
        user_profile = getattr(user, 'nuvia_profile', None)
        if user_profile:
            return user_profile.practice
        therapist_profile = getattr(user, 'therapist_profile', None)
        if therapist_profile:
            return therapist_profile.practice
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['practice'] = practice
        context['document_clients'] = practice.clients.all() if practice else []
        return context


class DocumentListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = ClientDocument
    template_name = 'documents/list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return ClientDocument.objects.none()
        return ClientDocument.objects.filter(practice=practice).select_related('client', 'uploaded_by')


class DocumentCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = ClientDocument
    form_class = ClientDocumentForm
    template_name = 'documents/form.html'
    success_url = reverse_lazy('documents:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        kwargs['uploaded_by'] = self.request.user
        return kwargs


class DocumentDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
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
        response = super().form_valid(form)
        if name:
            storage.delete(name)
        return response


class DocumentDownloadView(LoginRequiredMixin, PracticeContextMixin, View):
    def get(self, request, pk):
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
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.original_filename or document.file.name.rsplit('/', 1)[-1],
            content_type=document.content_type or 'application/octet-stream',
        )
