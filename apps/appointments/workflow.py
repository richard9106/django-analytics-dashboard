from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.accounts.access import has_practice_permission
from .models import Appointment


class SessionWorkflowMixin:
    """Keep create forms linked to a tenant-checked calendar session."""

    def get_workflow_appointment(self):
        if not hasattr(self, '_workflow_appointment'):
            self._workflow_appointment = None
            value = self.request.GET.get('appointment')
            if value and not getattr(self, 'object', None):
                if not value.isascii() or not value.isdigit() or len(value) > 18:
                    raise Http404
                self._workflow_appointment = get_object_or_404(
                    Appointment.objects.select_related('client', 'therapist__user'),
                    pk=value, practice=self.get_practice(),
                )
        return self._workflow_appointment

    def get_initial(self):
        initial = super().get_initial()
        appointment = self.get_workflow_appointment()
        if appointment:
            initial.update(appointment=appointment.pk, client=appointment.client_id)
            if self.permission_resource == 'clinical':
                initial['therapist'] = appointment.therapist_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['workflow_appointment'] = self.get_workflow_appointment()
        return context

    def get_success_url(self):
        appointment = self.get_workflow_appointment()
        if (appointment and self.object.appointment_id == appointment.pk
                and has_practice_permission(self.request.user, 'appointments', 'edit')):
            return reverse('appointments:edit', args=[appointment.pk])
        return super().get_success_url()
