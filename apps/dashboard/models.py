from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=140)
    email = models.EmailField(unique=True)
    segment = models.CharField(max_length=60, default='standard')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=140)
    sku = models.CharField(max_length=40, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Sale(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sales')
    quantity = models.PositiveIntegerField(default=1)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    sold_at = models.DateTimeField()

    class Meta:
        ordering = ['-sold_at']


class OperationalEvent(models.Model):
    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'

    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO)
    title = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
