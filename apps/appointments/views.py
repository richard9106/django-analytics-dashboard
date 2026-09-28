import calendar
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
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
    calendar_views = {'day', 'week', 'month', 'year'}

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

    def get_calendar_view(self):
        view = self.request.GET.get('view', 'month')
        return view if view in self.calendar_views else 'month'

    def get_anchor_date(self):
        date_value = self.request.GET.get('date')
        if date_value:
            try:
                return date.fromisoformat(date_value)
            except ValueError:
                pass
        return self.get_calendar_month()

    def get_period_navigation(self, view, anchor):
        if view == 'day':
            previous_value = (anchor - timedelta(days=1)).isoformat()
            next_value = (anchor + timedelta(days=1)).isoformat()
            return f'?view=day&date={previous_value}', f'?view=day&date={next_value}'
        if view == 'week':
            week_start = anchor - timedelta(days=anchor.weekday())
            return f'?view=week&date={(week_start - timedelta(days=7)).isoformat()}', f'?view=week&date={(week_start + timedelta(days=7)).isoformat()}'
        if view == 'year':
            return f'?view=year&date={date(anchor.year - 1, 1, 1).isoformat()}', f'?view=year&date={date(anchor.year + 1, 1, 1).isoformat()}'
        month_start = anchor.replace(day=1)
        previous_month = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return f'?view=month&month={previous_month:%Y-%m}', f'?view=month&month={next_month:%Y-%m}'

    def get_calendar_context(self, appointments):
        selected_view = self.get_calendar_view()
        anchor = self.get_anchor_date()
        month_start = self.get_calendar_month() if selected_view == 'month' else anchor.replace(day=1)
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

        week_start = anchor - timedelta(days=anchor.weekday())
        week_days = []
        for index in range(7):
            current_day = week_start + timedelta(days=index)
            week_days.append({
                'date': current_day,
                'is_today': current_day == today,
                'appointments': appointments_by_date.get(current_day, []),
            })

        year_months = []
        for month_number in range(1, 13):
            current_month = date(anchor.year, month_number, 1)
            month_count = sum(1 for appointment in appointments if timezone.localtime(appointment.starts_at).date().replace(day=1) == current_month)
            year_months.append({
                'date': current_month,
                'label': current_month.strftime('%B'),
                'count': month_count,
                'href': f'?view=month&month={current_month:%Y-%m}',
            })

        previous_period, next_period = self.get_period_navigation(selected_view, anchor)
        period_labels = {
            'day': anchor.strftime('%A, %B %-d'),
            'week': f"{week_start.strftime('%b %-d')} - {(week_start + timedelta(days=6)).strftime('%b %-d, %Y')}",
            'month': month_start.strftime('%B %Y'),
            'year': str(anchor.year),
        }

        return {
            'calendar_view': selected_view,
            'calendar_weeks': weeks,
            'calendar_period_label': period_labels[selected_view],
            'calendar_anchor_date': anchor,
            'calendar_week_days': week_days,
            'calendar_day_appointments': appointments_by_date.get(anchor, []),
            'calendar_year_months': year_months,
            'previous_period_url': previous_period,
            'next_period_url': next_period,
            'today_period_url': '?view=day&date=' + today.isoformat(),
            'month_view_url': f'?view=month&month={month_start:%Y-%m}',
            'week_view_url': f'?view=week&date={anchor.isoformat()}',
            'day_view_url': f'?view=day&date={anchor.isoformat()}',
            'year_view_url': f'?view=year&date={date(anchor.year, 1, 1).isoformat()}',
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


class AppointmentRescheduleView(LoginRequiredMixin, PracticeContextMixin, View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment.objects.filter(practice=self.get_practice()), pk=pk)
        date_value = request.POST.get('date', '')
        time_value = request.POST.get('time', '')
        try:
            selected_date = date.fromisoformat(date_value)
            selected_time = datetime.strptime(time_value, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Choose a valid date and time to move the appointment.')
            return redirect('appointments:list')

        duration = appointment.ends_at - appointment.starts_at
        appointment.starts_at = timezone.make_aware(datetime.combine(selected_date, selected_time))
        appointment.ends_at = appointment.starts_at + duration
        try:
            appointment.full_clean()
        except ValidationError as exc:
            messages.error(request, f'Appointment could not be moved: {exc}')
            return redirect('appointments:list')
        appointment.save()
        sync_appointment_to_google(appointment)
        messages.success(request, 'Appointment moved successfully.')
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
