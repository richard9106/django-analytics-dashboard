from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from .forms import ClientForm
from .models import Client


class PracticeContextMixin(ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['practice'] = self.get_practice()
        return context


class ClientListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = Client
    template_name = 'clients/list.html'
    context_object_name = 'clients'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()

        return (
            Client.objects.filter(practice=practice)
            .select_related('primary_therapist__user')
            .order_by('last_name', 'first_name')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['client_therapists'] = practice.therapists.select_related('user') if practice else []
        context['note_appointments'] = practice.appointments.select_related('client', 'therapist__user') if practice else []
        context['billing_templates'] = practice.session_package_templates.filter(active=True) if practice else []
        context['billing_today'] = timezone.localdate()
        return context


class ClientCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Client'
        context['form_heading'] = 'Create a client profile'
        context['submit_label'] = 'Create client'
        return context


class ClientUpdateView(LoginRequiredMixin, PracticeContextMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()

        return Client.objects.filter(practice=practice)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Client'
        context['form_heading'] = 'Edit client profile'
        context['submit_label'] = 'Save changes'
        context['show_delete_action'] = True
        return context


class ClientDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = Client
    success_url = reverse_lazy('clients:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Client.objects.none()

        return Client.objects.filter(practice=practice)
