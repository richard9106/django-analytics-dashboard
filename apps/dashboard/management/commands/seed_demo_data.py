from decimal import Decimal
from random import choice, randint

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.dashboard.models import Customer, OperationalEvent, Product, Sale


class Command(BaseCommand):
    help = 'Create lightweight demo data for the analytics dashboard.'

    def handle(self, *args, **options):
        segments = ['standard', 'growth', 'enterprise']
        products = [
            Product.objects.get_or_create(sku='API-001', defaults={'name': 'API Starter', 'price': Decimal('49.00')})[0],
            Product.objects.get_or_create(sku='API-002', defaults={'name': 'API Pro', 'price': Decimal('149.00')})[0],
            Product.objects.get_or_create(sku='OPS-001', defaults={'name': 'Ops Insights', 'price': Decimal('99.00')})[0],
        ]
        customers = [
            Customer.objects.get_or_create(email=f'customer{i}@example.com', defaults={'name': f'Customer {i}', 'segment': choice(segments)})[0]
            for i in range(1, 16)
        ]
        if Sale.objects.count() == 0:
            for _ in range(60):
                product = choice(products)
                quantity = randint(1, 4)
                Sale.objects.create(
                    customer=choice(customers),
                    product=product,
                    quantity=quantity,
                    total=product.price * quantity,
                    sold_at=timezone.now() - timezone.timedelta(days=randint(0, 45)),
                )
        if OperationalEvent.objects.count() == 0:
            for title, level in [('Daily import completed', 'info'), ('Payment retries elevated', 'warning'), ('Webhook recovered', 'info')]:
                OperationalEvent.objects.create(title=title, level=level)
        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
