from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import SessionNoteForm
from .models import SessionNote


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
        if practice:
            context['note_clients'] = practice.clients.all()
            context['note_therapists'] = practice.therapists.select_related('user')
            context['note_appointments'] = practice.appointments.select_related('client', 'therapist__user')
        else:
            context['note_clients'] = []
            context['note_therapists'] = []
            context['note_appointments'] = []
        return context


class SessionNoteListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = SessionNote
    template_name = 'clinical/list.html'
    context_object_name = 'notes'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return (
            SessionNote.objects.filter(practice=practice)
            .select_related('client', 'therapist__user', 'appointment')
            .order_by('-created_at')
        )


class SessionNoteCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = SessionNote
    form_class = SessionNoteForm
    template_name = 'clinical/form.html'
    success_url = reverse_lazy('clinical:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Clinical Note'
        context['form_heading'] = 'Document a client session'
        context['submit_label'] = 'Create note'
        return context


class SessionNoteUpdateView(LoginRequiredMixin, PracticeContextMixin, UpdateView):
    model = SessionNote
    form_class = SessionNoteForm
    template_name = 'clinical/form.html'
    success_url = reverse_lazy('clinical:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return SessionNote.objects.filter(practice=practice)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Clinical Note'
        context['form_heading'] = 'Edit note details'
        context['submit_label'] = 'Save changes'
        context['show_delete_action'] = True
        return context


class SessionNoteDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = SessionNote
    success_url = reverse_lazy('clinical:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return SessionNote.objects.none()

        return SessionNote.objects.filter(practice=practice)
