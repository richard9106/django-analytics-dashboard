from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.access import get_practice_for_user, is_client_user
from apps.appointments.models import Appointment
from apps.billing.models import Invoice
from apps.clients.models import Client
from apps.clinical.models import SessionNote, TreatmentPlan
from apps.notifications.models import Notification
from apps.portal.models import ClientPortalRequest


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_client_user(request.user):
            return redirect('portal:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_greeting(self, hour):
        if hour < 12:
            return 'Good morning'
        if hour < 20:
            return 'Good afternoon'
        return 'Good evening'

    def get_date_label(self, value):
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        return f'{weekdays[value.weekday()]}, {months[value.month - 1]} {value.day}'

    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_tasks(self, practice):
        if not practice:
            return []

        open_note_count = SessionNote.objects.filter(
            practice=practice,
            is_locked=False,
        ).count()
        open_invoice_count = Invoice.objects.filter(
            practice=practice,
            status__in=[Invoice.Status.DRAFT, Invoice.Status.SENT, Invoice.Status.OVERDUE],
        ).count()
        pending_notification_count = Notification.objects.filter(
            practice=practice,
            status=Notification.Status.PENDING,
        ).count()
        open_portal_request_count = ClientPortalRequest.objects.filter(
            practice=practice,
            status__in=[ClientPortalRequest.Status.NEW, ClientPortalRequest.Status.REVIEWED],
        ).count()
        due_treatment_plan_count = TreatmentPlan.objects.filter(
            practice=practice,
            status__in=[TreatmentPlan.Status.ACTIVE, TreatmentPlan.Status.REVIEW_DUE],
            review_date__lte=timezone.localdate(),
        ).count()

        tasks = []
        if open_note_count:
            suffix = '' if open_note_count == 1 else 's'
            tasks.append({
                'label': 'Clinical documentation',
                'detail': f'{open_note_count} note{suffix} ready to review or lock',
                'tone': 'warning',
            })
        if open_invoice_count:
            suffix = '' if open_invoice_count == 1 else 's'
            tasks.append({
                'label': 'Billing follow-up',
                'detail': f'{open_invoice_count} invoice{suffix} need attention',
                'tone': 'brand',
            })
        if pending_notification_count:
            suffix = '' if pending_notification_count == 1 else 's'
            tasks.append({
                'label': 'Client notifications',
                'detail': f'{pending_notification_count} message{suffix} pending delivery',
                'tone': 'success',
            })
        if open_portal_request_count:
            suffix = '' if open_portal_request_count == 1 else 's'
            tasks.append({
                'label': 'Client portal requests',
                'detail': f'{open_portal_request_count} portal request{suffix} awaiting follow-up',
                'tone': 'brand',
            })
        if due_treatment_plan_count:
            suffix = '' if due_treatment_plan_count == 1 else 's'
            tasks.append({
                'label': 'Treatment plan reviews',
                'detail': f'{due_treatment_plan_count} treatment plan{suffix} due for review',
                'tone': 'warning',
            })

        return tasks

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        today = now.date()
        start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        end_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
        display_name = self.request.user.first_name or self.request.user.username
        practice = self.get_practice()
        today_appointments = Appointment.objects.none()
        recent_invoices = Invoice.objects.none()
        practice_clients = []
        practice_therapists = []
        monthly_revenue = 0
        active_client_count = 0

        if practice:
            today_appointments = (
                Appointment.objects.filter(
                    practice=practice,
                    starts_at__gte=start_of_day,
                    starts_at__lte=end_of_day,
                )
                .select_related('client', 'therapist__user')
                .order_by('starts_at')
            )
            recent_invoices = Invoice.objects.filter(practice=practice).select_related('client')[:6]
            practice_clients = practice.clients.all()
            practice_therapists = practice.therapists.select_related('user')
            monthly_revenue = Invoice.objects.filter(
                practice=practice,
                status=Invoice.Status.PAID,
                paid_at__year=today.year,
                paid_at__month=today.month,
            ).aggregate(total=Sum('amount'))['total'] or 0
            active_client_count = Client.objects.filter(
                practice=practice,
                status=Client.Status.ACTIVE,
            ).count()

        tasks = self.get_tasks(practice)
        context.update({
            'dashboard_greeting': self.get_greeting(now.hour),
            'dashboard_display_name': display_name,
            'dashboard_date_label': self.get_date_label(now),
            'practice': practice,
            'monthly_revenue': monthly_revenue,
            'active_client_count': active_client_count,
            'today_appointment_count': today_appointments.count(),
            'task_count': len(tasks),
            'today_appointments': today_appointments,
            'tasks': tasks,
            'recent_invoices': recent_invoices,
            'practice_clients': practice_clients,
            'practice_therapists': practice_therapists,
        })
        return context
