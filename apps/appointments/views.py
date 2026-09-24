import calendar
from datetime import date, datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, get_practice_for_user
from .google_calendar import delete_google_event_for_appointment, sync_appointment_to_google
from .models import Appointment, PracticeWorkingHour
from .forms import AppointmentForm, PracticeWorkingHourForm


class PracticeContextMixin(ClientPortalRedirectMixin):
    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        context['practice'] = practice
        context['client_therapists'] = practice.therapists.select_related('user') if practice else []
        return context


class AppointmentListView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = Appointment
    template_name = 'appointments/list.html'
    context_object_name = 'appointments'

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Appointment.objects.none()

        return (
            Appointment.objects.filter(practice=practice)
            .select_related('client', 'therapist__user')
            .order_by('starts_at')
        )

    def get_calendar_month(self):
        month_value = self.request.GET.get('month')
        if month_value:
            try:
                return datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
            except ValueError:
                pass
        return timezone.localdate().replace(day=1)

    def get_calendar_context(self, appointments):
        month_start = self.get_calendar_month()
        previous_month = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month)
        today = timezone.localdate()

        appointments_by_date = {}
        for appointment in appointments:
            local_date = timezone.localtime(appointment.starts_at).date()
            appointments_by_date.setdefault(local_date, []).append(appointment)

        weeks = []
        for week in month_dates:
            weeks.append([
                {
                    'date': day,
                    'in_month': day.month == month_start.month,
                    'is_today': day == today,
                    'appointments': appointments_by_date.get(day, []),
                }
                for day in week
            ])

        return {
            'calendar_weeks': weeks,
            'calendar_month_label': month_start.strftime('%B %Y'),
            'previous_month': previous_month.strftime('%Y-%m'),
            'next_month': next_month.strftime('%Y-%m'),
            'weekday_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_calendar_context(context['appointments']))
        practice = self.get_practice()
        context['appointment_clients'] = practice.clients.all() if practice else []
        context['appointment_therapists'] = practice.therapists.select_related('user') if practice else []
        return context


class AppointmentCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/form.html'
    success_url = reverse_lazy('appointments:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        date_value = self.request.GET.get('date')
        if date_value:
            try:
                selected_date = date.fromisoformat(date_value)
            except ValueError:
                return initial
            starts_at = timezone.make_aware(datetime.combine(selected_date, time(hour=9)))
            initial['starts_at'] = starts_at
            initial['ends_at'] = starts_at + timedelta(minutes=50)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'New Appointment'
        context['form_heading'] = 'Schedule a session'
        context['submit_label'] = 'Create appointment'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_appointment_to_google(self.object)
        repeat_count = form.cleaned_data.get('repeat_weekly_count') or 1
        if repeat_count > 1:
            delta = self.object.ends_at - self.object.starts_at
            for index in range(1, repeat_count):
                appointment = Appointment(
                    practice=self.object.practice,
                    client=self.object.client,
                    therapist=self.object.therapist,
                    starts_at=self.object.starts_at + timedelta(weeks=index),
                    ends_at=self.object.starts_at + timedelta(weeks=index) + delta,
                    status=self.object.status,
                    appointment_type=self.object.appointment_type,
                    location=self.object.location,
                    meeting_url=self.object.meeting_url,
                    notes=self.object.notes,
                )
                appointment.full_clean()
                appointment.save()
                sync_appointment_to_google(appointment)
        return response


class AppointmentUpdateView(LoginRequiredMixin, PracticeContextMixin, UpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/form.html'
    success_url = reverse_lazy('appointments:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Appointment.objects.none()

        return Appointment.objects.filter(practice=practice)

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Appointment'
        context['form_heading'] = 'Edit session details'
        context['submit_label'] = 'Save changes'
        context['show_delete_action'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_appointment_to_google(self.object)
        return response


class AppointmentDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = Appointment
    success_url = reverse_lazy('appointments:list')

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Appointment.objects.none()

        return Appointment.objects.filter(practice=practice)

    def form_valid(self, form):
        try:
            delete_google_event_for_appointment(self.object)
        except Exception:
            pass
        return super().form_valid(form)


class AppointmentGoogleSyncView(LoginRequiredMixin, PracticeContextMixin, View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment.objects.filter(practice=self.get_practice()), pk=pk)
        sync_appointment_to_google(appointment)
        return redirect('appointments:list')


class AvailabilitySettingsView(LoginRequiredMixin, PracticeContextMixin, ListView):
    model = PracticeWorkingHour
    template_name = 'settings/availability.html'
    context_object_name = 'working_hours'

    def get_queryset(self):
        practice = self.get_practice()
        return PracticeWorkingHour.objects.filter(practice=practice) if practice else PracticeWorkingHour.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['working_hour_form'] = PracticeWorkingHourForm(practice=self.get_practice())
        return context


class WorkingHourCreateView(LoginRequiredMixin, PracticeContextMixin, CreateView):
    model = PracticeWorkingHour
    form_class = PracticeWorkingHourForm
    template_name = 'settings/availability_form.html'
    success_url = reverse_lazy('practice_settings:availability')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs


class WorkingHourDeleteView(LoginRequiredMixin, PracticeContextMixin, DeleteView):
    model = PracticeWorkingHour
    success_url = reverse_lazy('practice_settings:availability')

    def get_queryset(self):
        practice = self.get_practice()
        return PracticeWorkingHour.objects.filter(practice=practice) if practice else PracticeWorkingHour.objects.none()
