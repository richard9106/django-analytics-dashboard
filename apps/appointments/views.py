import calendar
import uuid
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.access import ClientPortalRedirectMixin, PracticePermissionMixin, get_practice_for_user
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


class AppointmentListView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'appointments'
    model = Appointment
    template_name = 'appointments/list.html'
    context_object_name = 'appointments'
    calendar_views = {'day', 'week', 'month'}
    calendar_start_hour = 7
    calendar_end_hour = 20
    calendar_hour_height = 72

    def get_queryset(self):
        practice = self.get_practice()
        if not practice:
            return Appointment.objects.none()

        appointments = (
            Appointment.objects.filter(practice=practice)
            .select_related('client', 'therapist__user')
            .order_by('starts_at')
        )
        filters = self.get_calendar_filters()
        if filters['q']:
            appointments = appointments.filter(
                Q(client__first_name__icontains=filters['q'])
                | Q(client__last_name__icontains=filters['q'])
                | Q(client__email__icontains=filters['q'])
            )
        if filters['therapist'].isdigit():
            appointments = appointments.filter(therapist_id=filters['therapist'])
        if filters['status'] in dict(Appointment.Status.choices):
            appointments = appointments.filter(status=filters['status'])
        if filters['appointment_type'] in dict(Appointment.AppointmentType.choices):
            appointments = appointments.filter(appointment_type=filters['appointment_type'])
        if filters['sync_status'] in dict(Appointment.SyncStatus.choices):
            appointments = appointments.filter(sync_status=filters['sync_status'])
        return appointments

    def get_calendar_filters(self):
        return {
            'q': self.request.GET.get('q', '').strip(),
            'therapist': self.request.GET.get('therapist', ''),
            'status': self.request.GET.get('status', ''),
            'appointment_type': self.request.GET.get('appointment_type', ''),
            'sync_status': self.request.GET.get('sync_status', ''),
        }

    def calendar_url(self, **updates):
        params = self.request.GET.copy()
        for key, value in updates.items():
            if value is None:
                params.pop(key, None)
            else:
                params[key] = value
        return '?' + params.urlencode()

    def get_calendar_month(self):
        month_value = self.request.GET.get('month')
        if month_value:
            try:
                return datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
            except ValueError:
                pass
        return timezone.localdate().replace(day=1)

    def get_calendar_view(self):
        view = self.request.GET.get('view', 'week')
        return view if view in self.calendar_views else 'week'

    def get_anchor_date(self):
        date_value = self.request.GET.get('date')
        if date_value:
            try:
                return date.fromisoformat(date_value)
            except ValueError:
                pass
        return timezone.localdate()

    def get_period_navigation(self, view, anchor):
        if view == 'day':
            previous_value = (anchor - timedelta(days=1)).isoformat()
            next_value = (anchor + timedelta(days=1)).isoformat()
            return self.calendar_url(view='day', date=previous_value), self.calendar_url(view='day', date=next_value)
        if view == 'week':
            week_start = anchor - timedelta(days=anchor.weekday())
            return self.calendar_url(view='week', date=(week_start - timedelta(days=7)).isoformat()), self.calendar_url(view='week', date=(week_start + timedelta(days=7)).isoformat())
        month_start = anchor.replace(day=1)
        previous_month = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return self.calendar_url(view='month', month=f'{previous_month:%Y-%m}', date=None), self.calendar_url(view='month', month=f'{next_month:%Y-%m}', date=None)

    def get_timed_event(self, appointment):
        local_start = timezone.localtime(appointment.starts_at)
        local_end = timezone.localtime(appointment.ends_at)
        start_minutes = max(0, (local_start.hour - self.calendar_start_hour) * 60 + local_start.minute)
        duration_minutes = max(25, int((local_end - local_start).total_seconds() // 60))
        top = int(start_minutes * (self.calendar_hour_height / 60))
        height = int(duration_minutes * (self.calendar_hour_height / 60))
        max_height = (self.calendar_end_hour - self.calendar_start_hour + 1) * self.calendar_hour_height
        if top > max_height:
            top = max_height - 28
        return {
            'appointment': appointment,
            'style': f'top: {top}px; min-height: {max(34, height)}px;',
        }

    def get_calendar_context(self, appointments):
        selected_view = self.get_calendar_view()
        anchor = self.get_anchor_date()
        month_start = self.get_calendar_month() if selected_view == 'month' else anchor.replace(day=1)
        month_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month)
        today = timezone.localdate()
        configured_hours = list(self.get_practice().working_hours.filter(active=True)) if self.get_practice() else []
        hours_by_weekday = {}
        for working_hour in configured_hours:
            hours_by_weekday.setdefault(working_hour.weekday, []).append(working_hour)

        def availability_for_day(current_day):
            if not configured_hours:
                return {'configured': False, 'blocks': []}
            day_hours = hours_by_weekday.get(current_day.weekday(), [])
            cursor = self.calendar_start_hour * 60
            end_of_grid = self.calendar_end_hour * 60
            blocks = []
            for working_hour in sorted(day_hours, key=lambda hour: hour.starts_at):
                start_minutes = max(cursor, working_hour.starts_at.hour * 60 + working_hour.starts_at.minute)
                end_minutes = min(end_of_grid, working_hour.ends_at.hour * 60 + working_hour.ends_at.minute)
                if start_minutes > cursor:
                    blocks.append({
                        'style': f'top: {54 + (cursor - self.calendar_start_hour * 60) * (self.calendar_hour_height / 60)}px; height: {(start_minutes - cursor) * (self.calendar_hour_height / 60)}px;',
                    })
                cursor = max(cursor, end_minutes)
            if cursor < end_of_grid:
                blocks.append({
                    'style': f'top: {54 + (cursor - self.calendar_start_hour * 60) * (self.calendar_hour_height / 60)}px; height: {(end_of_grid - cursor) * (self.calendar_hour_height / 60)}px;',
                })
            return {'configured': True, 'blocks': blocks}

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
                    'outside_availability': availability_for_day(day)['configured'] and not hours_by_weekday.get(day.weekday()),
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
                'timed_events': [self.get_timed_event(appointment) for appointment in appointments_by_date.get(current_day, [])],
                'availability_blocks': availability_for_day(current_day)['blocks'],
            })

        day_timed_events = [self.get_timed_event(appointment) for appointment in appointments_by_date.get(anchor, [])]
        day_availability = availability_for_day(anchor)

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
        now = timezone.localtime()
        current_minutes = (now.hour - self.calendar_start_hour) * 60 + now.minute
        current_time_top = int(current_minutes * (self.calendar_hour_height / 60)) + 54
        show_current_time = self.calendar_start_hour <= now.hour <= self.calendar_end_hour
        view_switch_date = today if selected_view == 'month' and month_start.year == today.year and month_start.month == today.month else anchor

        return {
            'calendar_view': selected_view,
            'calendar_weeks': weeks,
            'calendar_period_label': period_labels[selected_view],
            'calendar_anchor_date': anchor,
            'calendar_week_days': week_days,
            'calendar_day_appointments': appointments_by_date.get(anchor, []),
            'calendar_day_timed_events': day_timed_events,
            'calendar_day_availability_blocks': day_availability['blocks'],
            'calendar_availability_configured': bool(configured_hours),
            'calendar_year_months': year_months,
            'calendar_hours': [time(hour=hour) for hour in range(self.calendar_start_hour, self.calendar_end_hour + 1)],
            'calendar_grid_height': (self.calendar_end_hour - self.calendar_start_hour + 1) * self.calendar_hour_height,
            'calendar_grid_config': {
                'startHour': self.calendar_start_hour,
                'endHour': self.calendar_end_hour,
                'hourHeight': self.calendar_hour_height,
                'defaultDurationMinutes': 50,
            },
            'calendar_current_time_top': current_time_top,
            'calendar_show_current_time': show_current_time,
            'calendar_today': today,
            'previous_period_url': previous_period,
            'next_period_url': next_period,
            'today_period_url': self.calendar_url(view='day', date=today.isoformat()),
            'month_view_url': self.calendar_url(view='month', month=f'{month_start:%Y-%m}', date=None),
            'week_view_url': self.calendar_url(view='week', date=view_switch_date.isoformat(), month=None),
            'day_view_url': self.calendar_url(view='day', date=view_switch_date.isoformat(), month=None),
            'calendar_filters': self.get_calendar_filters(),
            'appointment_status_choices': Appointment.Status.choices,
            'appointment_type_choices': Appointment.AppointmentType.choices,
            'sync_status_choices': Appointment.SyncStatus.choices,
            'weekday_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_calendar_context(context['appointments']))
        practice = self.get_practice()
        context['appointment_clients'] = practice.clients.all() if practice else []
        context['appointment_therapists'] = practice.therapists.select_related('user') if practice else []
        return context


class AppointmentCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'appointments'
    permission_action = 'create'
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
        repeat_count = form.cleaned_data.get('repeat_weekly_count') or 1
        if repeat_count > 1:
            self.object.series_id = uuid.uuid4()
            self.object.save(update_fields=['series_id', 'updated_at'])
        sync_appointment_to_google(self.object)
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
                    series_id=self.object.series_id,
                )
                appointment.full_clean()
                appointment.save()
                sync_appointment_to_google(appointment)
        return response


class AppointmentUpdateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, UpdateView):
    permission_resource = 'appointments'
    permission_action = 'edit'
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


class AppointmentDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'appointments'
    permission_action = 'delete'
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


class AppointmentSeriesUpdateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'appointments'
    permission_action = 'edit'

    def post(self, request, pk):
        practice = self.get_practice()
        appointment = get_object_or_404(Appointment.objects.filter(practice=practice), pk=pk)
        if not appointment.series_id:
            messages.error(request, 'This appointment is not part of a recurring series.')
            return redirect('appointments:edit', pk=appointment.pk)
        original_start = appointment.starts_at
        form = AppointmentForm(request.POST, instance=appointment, practice=practice)
        if not form.is_valid():
            messages.error(request, 'Review the appointment details before updating the series.')
            return redirect('appointments:edit', pk=appointment.pk)
        updated = form.save(commit=False)
        start_delta = updated.starts_at - original_start
        duration = updated.ends_at - updated.starts_at
        future = list(Appointment.objects.filter(
            practice=practice, series_id=appointment.series_id,
            starts_at__gte=original_start, status=Appointment.Status.SCHEDULED,
        ))
        try:
            with transaction.atomic():
                for occurrence in future:
                    occurrence.client = updated.client
                    occurrence.therapist = updated.therapist
                    occurrence.starts_at = occurrence.starts_at + start_delta
                    occurrence.ends_at = occurrence.starts_at + duration
                    occurrence.appointment_type = updated.appointment_type
                    occurrence.status = updated.status
                    occurrence.location = updated.location
                    occurrence.meeting_url = updated.meeting_url
                    occurrence.notes = updated.notes
                    occurrence.full_clean()
                    occurrence.save()
        except ValidationError as exc:
            messages.error(request, f'Series could not be updated: {exc}')
            return redirect('appointments:edit', pk=appointment.pk)
        for occurrence in future:
            sync_appointment_to_google(occurrence)
        messages.success(request, f'Updated {len(future)} upcoming appointments in this series.')
        return redirect('appointments:list')


class AppointmentSeriesCancelView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'appointments'
    permission_action = 'edit'

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment.objects.filter(practice=self.get_practice()), pk=pk)
        if not appointment.series_id:
            messages.error(request, 'This appointment is not part of a recurring series.')
            return redirect('appointments:edit', pk=appointment.pk)
        future = list(Appointment.objects.filter(
            practice=appointment.practice, series_id=appointment.series_id,
            starts_at__gte=appointment.starts_at, status=Appointment.Status.SCHEDULED,
        ))
        for occurrence in future:
            occurrence.status = Appointment.Status.CANCELLED
            occurrence.save(update_fields=['status', 'updated_at'])
            try:
                delete_google_event_for_appointment(occurrence)
            except Exception:
                pass
        messages.success(request, f'Cancelled {len(future)} upcoming appointments in this series.')
        return redirect('appointments:list')


class AppointmentGoogleSyncView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'appointments'
    permission_action = 'edit'
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment.objects.filter(practice=self.get_practice()), pk=pk)
        sync_appointment_to_google(appointment)
        return redirect('appointments:list')


class AppointmentRescheduleView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, View):
    permission_resource = 'appointments'
    permission_action = 'edit'
    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('appointments:list')

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment.objects.filter(practice=self.get_practice()), pk=pk)
        date_value = request.POST.get('date', '')
        time_value = request.POST.get('time', '')
        try:
            selected_date = date.fromisoformat(date_value)
            selected_time = datetime.strptime(time_value, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Choose a valid date and time to move the appointment.')
            return redirect(self.get_success_url())

        duration = appointment.ends_at - appointment.starts_at
        appointment.starts_at = timezone.make_aware(datetime.combine(selected_date, selected_time))
        appointment.ends_at = appointment.starts_at + duration
        try:
            appointment.full_clean()
        except ValidationError as exc:
            messages.error(request, f'Appointment could not be moved: {exc}')
            return redirect(self.get_success_url())
        appointment.save()
        sync_appointment_to_google(appointment)
        messages.success(request, 'Appointment moved successfully.')
        return redirect(self.get_success_url())


class AvailabilitySettingsView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, ListView):
    permission_resource = 'appointments'
    model = PracticeWorkingHour
    template_name = 'settings/availability.html'
    context_object_name = 'working_hours'

    def get_queryset(self):
        practice = self.get_practice()
        return PracticeWorkingHour.objects.filter(practice=practice) if practice else PracticeWorkingHour.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['working_hour_form'] = PracticeWorkingHourForm(practice=self.get_practice())
        hours = list(context['working_hours'])
        context['working_hours_by_day'] = [
            {
                'value': weekday,
                'label': label,
                'hours': [hour for hour in hours if hour.weekday == weekday],
            }
            for weekday, label in PracticeWorkingHour.Weekday.choices
        ]
        return context


class WorkingHourCreateView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, CreateView):
    permission_resource = 'appointments'
    permission_action = 'edit'
    model = PracticeWorkingHour
    form_class = PracticeWorkingHourForm
    template_name = 'settings/availability_form.html'
    success_url = reverse_lazy('practice_settings:availability')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = self.get_practice()
        return kwargs


class WorkingHourDeleteView(LoginRequiredMixin, PracticePermissionMixin, PracticeContextMixin, DeleteView):
    permission_resource = 'appointments'
    permission_action = 'delete'
    model = PracticeWorkingHour
    success_url = reverse_lazy('practice_settings:availability')

    def get_queryset(self):
        practice = self.get_practice()
        return PracticeWorkingHour.objects.filter(practice=practice) if practice else PracticeWorkingHour.objects.none()
