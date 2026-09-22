from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from .models import Customer, OperationalEvent, Product, Sale


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        display_name = self.request.user.first_name or self.request.user.username
        sales_by_segment = (
            Sale.objects.values('customer__segment')
            .annotate(total=Sum('total'))
            .order_by('customer__segment')
        )
        context.update({
            'dashboard_greeting': self.get_greeting(now.hour),
            'dashboard_display_name': display_name,
            'dashboard_date_label': self.get_date_label(now),
            'total_revenue': Sale.objects.aggregate(total=Sum('total'))['total'] or 0,
            'customer_count': Customer.objects.count(),
            'active_product_count': Product.objects.filter(active=True).count(),
            'event_count': OperationalEvent.objects.count(),
            'recent_sales': Sale.objects.select_related('customer', 'product')[:8],
            'recent_events': OperationalEvent.objects.all()[:6],
            'chart_labels': [row['customer__segment'] for row in sales_by_segment],
            'chart_values': [float(row['total'] or 0) for row in sales_by_segment],
        })
        return context
