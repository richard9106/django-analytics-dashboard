from datetime import date
from decimal import Decimal, ROUND_CEILING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, F, Value, DecimalField
from django.db.models.functions import Coalesce, Greatest, TruncMonth
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView

from apps.accounts.access import PracticePermissionMixin, has_practice_permission, get_practice_for_user, is_client_user, permission_redirect
from apps.appointments.models import Appointment
from apps.billing.models import Invoice
from apps.clients.models import Client
from apps.clinical.models import SessionNote, TreatmentPlan
from apps.notifications.models import Notification
from apps.portal.models import ClientPortalRequest
from apps.practices.models import Practice
from apps.rate_limit import PostRateLimitMixin
from .forms import SupportContactForm, TaskForm
from .models import Task
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

    def can_view(self, resource):
        return has_practice_permission(self.request.user, resource, 'view')

    def get_tasks(self, practice):
        self.dashboard_task_count = 0
        if not practice or not self.can_view('tasks'):
            return []
        tasks = []
        def alert(resource, queryset, label, noun, detail, tone, url, action):
            if not self.can_view(resource):
                return
            count = queryset.count()
            if count:
                tasks.append({'label': label, 'detail': f"{count} {noun}{'' if count == 1 else 's'} {detail}",
                              'tone': tone, 'href': url, 'action_label': action})
        alert('clinical', SessionNote.objects.filter(practice=practice, is_locked=False),
              'Clinical documentation', 'note', 'ready to review or lock', 'warning',
              reverse('clinical:list') + '?status=draft', 'Review notes')
        alert('billing', Invoice.objects.filter(practice=practice, status__in=[Invoice.Status.DRAFT, Invoice.Status.SENT, Invoice.Status.OVERDUE]),
              'Billing follow-up', 'invoice', 'need attention', 'brand', reverse('billing:list'), 'Review invoices')
        alert('tasks', Notification.objects.filter(practice=practice, status=Notification.Status.PENDING),
              'Client notifications', 'message', 'pending delivery', 'success',
              reverse('practice_settings:integrations'), 'Review delivery setup')
        alert('requests', ClientPortalRequest.objects.filter(practice=practice, status__in=[ClientPortalRequest.Status.NEW, ClientPortalRequest.Status.REVIEWED]),
              'Client portal requests', 'portal request', 'awaiting follow-up', 'brand',
              reverse('portal_requests:list'), 'Review requests')
        alert('clinical', TreatmentPlan.objects.filter(practice=practice,
              status__in=[TreatmentPlan.Status.ACTIVE, TreatmentPlan.Status.REVIEW_DUE], review_date__lte=timezone.localdate()),
              'Treatment plan reviews', 'treatment plan', 'due for review', 'warning',
              reverse('clinical:treatment_plans') + '?review_to=' + timezone.localdate().isoformat(), 'Review plans')
        self.dashboard_task_count = len(tasks)
        if self.can_view('tasks'):
            manual_tasks = Task.objects.filter(practice=practice, assignee=self.request.user).exclude(status=Task.Status.DONE)
            self.dashboard_task_count += manual_tasks.count()
            for task in manual_tasks.select_related('assignee')[:50]:
                tasks.append({'manual': task, 'label': task.title, 'detail': task.description or 'Assigned follow-up',
                              'tone': 'manual', 'href': reverse('tasks_detail', args=[task.pk]), 'action_label': 'Open task'})
        return tasks

    def get_performance_months(self, practice, today):
        if not practice:
            return []

        def shift_month(value, offset):
            month_index = value.year * 12 + value.month - 1 + offset
            return date(month_index // 12, month_index % 12 + 1, 1)

        months = []
        start_date = shift_month(today.replace(day=1), -5)
        end_date = shift_month(today.replace(day=1), 1)
        start_at = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
        end_at = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.min.time()))
        revenues = {}
        volumes = {}
        if self.can_view('billing'):
            revenues = {row['month'].date(): row['total'] for row in Invoice.objects.filter(
                practice=practice, status=Invoice.Status.PAID, paid_at__gte=start_at, paid_at__lt=end_at,
            ).annotate(month=TruncMonth('paid_at')).values('month').annotate(total=Sum('amount')).order_by()}
        if self.can_view('appointments'):
            volumes = {row['month'].date(): row['total'] for row in Appointment.objects.filter(
                practice=practice, starts_at__gte=start_at, starts_at__lt=end_at,
            ).annotate(month=TruncMonth('starts_at')).values('month').annotate(total=Count('pk')).order_by()}
        for offset in range(-5, 1):
            month_start = shift_month(today.replace(day=1), offset)
            months.append({'label': month_start.strftime('%b'), 'revenue': revenues.get(month_start, 0),
                           'appointments': volumes.get(month_start, 0)})

        max_revenue = max((month['revenue'] for month in months), default=0)
        max_appointments = max((month['appointments'] for month in months), default=0)
        for month in months:
            month['revenue_height'] = int(month['revenue'] / max_revenue * 100) if max_revenue else 0
            month['appointment_height'] = int(month['appointments'] / max_appointments * 100) if max_appointments else 0
        return months

    def get_onboarding_steps(self, practice):
        if not practice:
            return []
        steps = []
        if has_practice_permission(self.request.user, 'clients', 'create') and not practice.clients.exists():
            steps.append({'label': 'Add your first client', 'url': reverse('clients:create'), 'complete': False})
        if has_practice_permission(self.request.user, 'appointments', 'edit'):
            if not practice.working_hours.exists() and not practice.availability_overrides.exists():
                steps.append({'label': 'Set practice availability', 'url': reverse('appointments:list') + '?view=week#availability-changes', 'complete': False})
        if has_practice_permission(self.request.user, 'appointments', 'create') and not practice.appointments.exists():
            steps.append({'label': 'Schedule your first session', 'url': reverse('appointments:create'), 'complete': False})
        return steps

    def get_dashboard_charts(self, practice, today, months):
        # Fixed SVG geometry and locale-independent numbers; labels retain exact values.
        maximum = max((Decimal(month['revenue']) for month in months), default=Decimal('0'))
        scale = Decimal('1')
        if maximum > 0:
            magnitude = Decimal('10') ** maximum.adjusted()
            scale = (maximum / magnitude).to_integral_value(rounding=ROUND_CEILING) * magnitude
        points = []
        chart_months = []
        for index, month in enumerate(months):
            x = 36 + (468 * index / max(1, len(months) - 1))
            y = 148 - float(Decimal(month['revenue']) / scale) * 132
            points.append(f'{x:.1f},{y:.1f}')
            chart_months.append({'label': month['label'], 'x': f'{x:.1f}', 'revenue': month['revenue']})
        result = {
            'revenue_chart_points': ' '.join(points),
            'revenue_chart_area': '36,148 ' + ' '.join(points) + ' 504,148',
            'revenue_chart_ticks': [{'value': scale, 'y': 16}, {'value': scale / 2, 'y': 82}, {'value': 0, 'y': 148}],
            'revenue_chart_months': chart_months,
            'revenue_chart_has_data': maximum > 0,
            'session_status_segments': [], 'session_status_total': 0,
            'invoice_status_breakdown': [], 'invoice_status_total': 0,
        }
        if not practice:
            return result
        index = today.year * 12 + today.month - 1
        first = date((index - 5) // 12, (index - 5) % 12 + 1, 1)
        following = date((index + 1) // 12, (index + 1) % 12 + 1, 1)
        start = timezone.make_aware(timezone.datetime.combine(first, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(following, timezone.datetime.min.time()))
        if self.can_view('appointments'):
            counts = dict(Appointment.objects.filter(practice=practice, starts_at__gte=start, starts_at__lt=end)
                          .values('status').annotate(total=Count('pk')).values_list('status', 'total').order_by())
            total = sum(counts.values())
            result['session_status_total'] = total
            cursor = 0
            colors = ['#7052D9', '#14B8A6', '#94A3B8', '#F59E0B']
            for (status, label), color in zip(Appointment.Status.choices, colors):
                count = counts.get(status, 0)
                if not count:
                    continue
                share = count / total * 100
                result['session_status_segments'].append({'label': label, 'count': count, 'color': color,
                    'start': f'{cursor:.3f}', 'share': f'{share:.3f}', 'gap': f'{100-share:.3f}'})
                cursor += share
        if self.can_view('billing'):
            counts = dict(Invoice.objects.filter(practice=practice, created_at__gte=start, created_at__lt=end)
                          .values('status').annotate(total=Count('pk')).values_list('status', 'total').order_by())
            maximum_count = max(counts.values(), default=0)
            result['invoice_status_total'] = sum(counts.values())
            colors = ['#94A3B8', '#7052D9', '#14B8A6', '#F36F56', '#CBD5E1']
            for (status, label), color in zip(Invoice.Status.choices, colors):
                count = counts.get(status, 0)
                result['invoice_status_breakdown'].append({'label': label, 'count': count, 'color': color,
                    'width': f'{count / maximum_count * 100:.3f}' if maximum_count else '0'})
        return result

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

        billing_summary = {'outstanding_balance': Decimal('0.00'), 'overdue_invoice_count': 0, 'open_invoice_count': 0}
        today_appointment_count = 0
        if practice and self.can_view('appointments'):
            today_appointments = (
                Appointment.objects.filter(
                    practice=practice,
                    starts_at__gte=start_of_day,
                    starts_at__lte=end_of_day,
                )
                .select_related('client', 'therapist__user')
                .order_by('starts_at')
            )
            today_appointment_count = today_appointments.count()
            today_appointments = today_appointments[:50]
        if practice and self.can_view('billing'):
            recent_invoices = Invoice.objects.filter(practice=practice).select_related('client')[:6]
            monthly_revenue = performance_months[-1]['revenue'] if performance_months else 0
            money = DecimalField(max_digits=12, decimal_places=2)
            unpaid = Invoice.objects.filter(practice=practice, status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE]).annotate(
                received=Coalesce(Sum('payments__amount'), Value(Decimal('0.00')), output_field=money),
            ).annotate(balance=Greatest(F('amount') - F('received'), Value(Decimal('0.00')), output_field=money))
            billing_summary = unpaid.aggregate(
                outstanding_balance=Coalesce(Sum('balance'), Value(Decimal('0.00')), output_field=money),
                overdue_invoice_count=Count('pk', filter=Q(balance__gt=0) & (Q(status=Invoice.Status.OVERDUE) | Q(due_date__lt=today))),
                open_invoice_count=Count('pk', filter=Q(balance__gt=0)),
            )
        if practice and self.can_view('clients'):
            active_client_count = Client.objects.filter(practice=practice, status=Client.Status.ACTIVE).count()
        if practice and has_practice_permission(self.request.user, 'appointments', 'create'):
            practice_clients = practice.clients.all()
        if practice and (has_practice_permission(self.request.user, 'appointments', 'create') or has_practice_permission(self.request.user, 'clients', 'create')):
            practice_therapists = practice.therapists.select_related('user')

        tasks = self.get_tasks(practice)
        context.update({
            'dashboard_greeting': self.get_greeting(now.hour),
            'dashboard_display_name': display_name,
            'dashboard_date_label': self.get_date_label(now),
            'show_dashboard_tour': self.request.GET.get('tour') == '1',
            'practice': practice,
            'monthly_revenue': monthly_revenue,
            'active_client_count': active_client_count,
            'today_appointment_count': today_appointment_count,
            'task_count': self.dashboard_task_count,
            'tasks_shown': len(tasks),
            'today_appointments': today_appointments,
            'tasks': tasks,
            'recent_invoices': recent_invoices,
            'practice_clients': practice_clients,
            'practice_therapists': practice_therapists,
            'performance_months': performance_months,
        })
        context.update(billing_summary)
        context['dashboard_onboarding_steps'] = self.get_onboarding_steps(practice)
        context.update(self.get_dashboard_charts(practice, today, performance_months))
        return context


class HealthCheckView(TemplateView):
    def get(self, request, *args, **kwargs):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except Exception:
            return JsonResponse({'status': 'unhealthy'}, status=503)
        return JsonResponse({'status': 'ok'})


class StaffMonitoringView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/monitoring.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        health_checks = []
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            health_checks.append({'label': 'Database', 'ok': True, 'detail': 'PostgreSQL query succeeded.'})
        except Exception as error:
            health_checks.append({'label': 'Database', 'ok': False, 'detail': error.__class__.__name__})

        health_checks.extend([
            {'label': 'Email delivery', 'ok': bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL), 'detail': 'SMTP configuration present.' if settings.EMAIL_HOST else 'SMTP host is missing.'},
            {'label': 'Stripe', 'ok': bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET), 'detail': 'Secret and webhook configuration present.' if settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET else 'Stripe configuration is incomplete.'},
            {'label': 'Google OAuth', 'ok': bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET), 'detail': 'OAuth credentials present.' if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET else 'OAuth credentials are missing.'},
            {'label': 'Cloudflare R2', 'ok': settings.DJANGO_STORAGE_BACKEND == 'r2' and bool(getattr(settings, 'AWS_ACCESS_KEY_ID', '')), 'detail': 'R2 storage is configured.' if settings.DJANGO_STORAGE_BACKEND == 'r2' and getattr(settings, 'AWS_ACCESS_KEY_ID', '') else 'Local media storage is active.'},
        ])
        context['health_checks'] = health_checks
        context['monitoring_metrics'] = [
            ('Practices', Practice.objects.count()),
            ('Users', get_user_model().objects.count()),
            ('Clients', Client.objects.count()),
            ('Open invoices', Invoice.objects.filter(status__in=[Invoice.Status.DRAFT, Invoice.Status.SENT, Invoice.Status.OVERDUE]).count()),
            ('Open tasks', Task.objects.exclude(status=Task.Status.DONE).count()),
            ('Failed notifications', Notification.objects.filter(status=Notification.Status.FAILED).count()),
        ]
        return context


class TaskListView(LoginRequiredMixin, PracticePermissionMixin, TemplateView):
    permission_resource = 'tasks'
    template_name = 'dashboard/tasks.html'

    def dispatch(self, request, *args, **kwargs):
        if is_client_user(request.user):
            return redirect('portal:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = get_practice_for_user(self.request.user)
        context['task_practice'] = practice
        context['task_form'] = TaskForm(practice=practice)
        context['form'] = context['task_form']
        context['tasks'] = Task.objects.filter(practice=practice).select_related('assignee', 'created_by') if practice else Task.objects.none()
        return context


class TaskCreateView(LoginRequiredMixin, PracticePermissionMixin, FormView):
    permission_resource = 'tasks'
    permission_action = 'create'
    template_name = 'dashboard/tasks.html'
    form_class = TaskForm

    def dispatch(self, request, *args, **kwargs):
        if is_client_user(request.user):
            return redirect('portal:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['practice'] = get_practice_for_user(self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = get_practice_for_user(self.request.user)
        context['task_practice'] = practice
        context['tasks'] = Task.objects.filter(practice=practice).select_related('assignee', 'created_by') if practice else Task.objects.none()
        return context

    def form_valid(self, form):
        task = form.save(commit=False)
        task.practice = get_practice_for_user(self.request.user)
        task.created_by = self.request.user
        task.save()
        messages.success(self.request, 'Task assigned to your team.')
        return redirect('tasks_list')

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form, task_form=form))


class TaskDetailView(LoginRequiredMixin, PracticePermissionMixin, DetailView):
    permission_resource = 'tasks'
    model = Task
    template_name = 'dashboard/task_detail.html'
    context_object_name = 'task'

    def get_queryset(self):
        return Task.objects.filter(practice=get_practice_for_user(self.request.user)).select_related('assignee', 'created_by', 'practice')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['practice'] = self.object.practice
        context['can_update_task'] = has_practice_permission(self.request.user, 'tasks', 'edit') and self.request.user.pk in {self.object.assignee_id, self.object.created_by_id}
        return context


class TaskStatusUpdateView(LoginRequiredMixin, PracticePermissionMixin, TemplateView):
    permission_resource = 'tasks'
    permission_action = 'edit'
    def post(self, request, pk):
        practice = get_practice_for_user(request.user)
        task = get_object_or_404(Task, pk=pk, practice=practice)
        if task.assignee_id != request.user.id and task.created_by_id != request.user.id:
            return permission_redirect(request, 'Only the assigned therapist or task creator can update this task.')
        status = request.POST.get('status')
        if status in dict(Task.Status.choices):
            task.status = status
            task.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Task status updated.')
        destination = request.POST.get('next')
        if destination == 'task_detail':
            return redirect('tasks_detail', pk=task.pk)
        return redirect('dashboard' if destination == 'dashboard' else 'tasks_list')


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


class SupportContactView(PostRateLimitMixin, FormView):
    template_name = 'support/contact.html'
    form_class = SupportContactForm
    success_url = '/help/contact/?sent=1'
    rate_limit_scope = 'support-contact'
    rate_limit_count = 5
    rate_limit_seconds = 3600

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
