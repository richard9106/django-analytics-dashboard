from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from apps.accounts.access import get_practice_for_user, is_client_user
from apps.appointments.models import Appointment
from apps.billing.models import Invoice
from apps.clients.models import Client
from apps.clinical.models import SessionNote, TreatmentPlan
from apps.notifications.models import Notification
from apps.portal.models import ClientPortalRequest
from .forms import SupportContactForm
from .support import FAQS


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

    def get_performance_months(self, practice, today):
        if not practice:
            return []

        def shift_month(value, offset):
            month_index = value.year * 12 + value.month - 1 + offset
            return date(month_index // 12, month_index % 12 + 1, 1)

        months = []
        for offset in range(-5, 1):
            month_start = shift_month(today.replace(day=1), offset)
            next_month = shift_month(month_start, 1)
            start_at = timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time()))
            end_at = timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
            revenue = Invoice.objects.filter(
                practice=practice,
                status=Invoice.Status.PAID,
                paid_at__gte=start_at,
                paid_at__lt=end_at,
            ).aggregate(total=Sum('amount'))['total'] or 0
            appointments = Appointment.objects.filter(
                practice=practice,
                starts_at__gte=start_at,
                starts_at__lt=end_at,
            ).count()
            months.append({
                'label': month_start.strftime('%b'),
                'revenue': revenue,
                'appointments': appointments,
            })

        max_revenue = max((month['revenue'] for month in months), default=0)
        max_appointments = max((month['appointments'] for month in months), default=0)
        for month in months:
            month['revenue_height'] = int(month['revenue'] / max_revenue * 100) if max_revenue else 6
            month['appointment_height'] = int(month['appointments'] / max_appointments * 100) if max_appointments else 6
        return months

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
        performance_months = self.get_performance_months(practice, today)

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
            'show_dashboard_tour': self.request.GET.get('tour') == '1',
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
            'performance_months': performance_months,
        })
        return context


class HelpCenterView(TemplateView):
    template_name = 'support/help_center.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()
        faqs = FAQS
        if query:
            terms = query.lower().split()
            faqs = [faq for faq in FAQS if all(term in f"{faq['question']} {faq['answer']} {faq['tags']}".lower() for term in terms)]
        context.update({'faqs': faqs, 'query': query})
        return context


class SupportContactView(FormView):
    template_name = 'support/contact.html'
    form_class = SupportContactForm
    success_url = '/help/contact/?sent=1'

    def get_initial(self):
        initial = super().get_initial()
        if self.request.user.is_authenticated:
            initial.update({'name': self.request.user.get_full_name(), 'email': self.request.user.email})
        return initial

    def form_valid(self, form):
        message = EmailMessage(
            subject=f"NuviaMy support: {form.cleaned_data['topic']}",
            body=(
                f"Name: {form.cleaned_data['name']}\n"
                f"Email: {form.cleaned_data['email']}\n"
                f"Topic: {form.cleaned_data['topic']}\n\n"
                f"{form.cleaned_data['message']}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.SUPPORT_EMAIL],
            reply_to=[form.cleaned_data['email']],
        )
        try:
            message.send(fail_silently=False)
        except Exception:
            messages.error(self.request, 'Support is temporarily unavailable. Please try again later.')
            return self.form_invalid(form)
        return super().form_valid(form)


class HomePageView(TemplateView):
    template_name = 'marketing/home.html'


class PricingPageView(TemplateView):
    template_name = 'marketing/pricing.html'


class FeaturesPageView(TemplateView):
    template_name = 'marketing/features.html'


class TherapyPracticeManagementPageView(TemplateView):
    template_name = 'marketing/therapy_practice_management.html'


class TherapySchedulingPageView(TemplateView):
    template_name = 'marketing/therapy_scheduling.html'


class ClinicalNotesSoftwarePageView(TemplateView):
    template_name = 'marketing/clinical_notes_software.html'


class ClientPortalSoftwarePageView(TemplateView):
    template_name = 'marketing/client_portal_software.html'


class MentalHealthBillingSoftwarePageView(TemplateView):
    template_name = 'marketing/mental_health_billing_software.html'
