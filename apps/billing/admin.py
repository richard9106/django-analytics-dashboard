from django.contrib import admin

from .models import Invoice, Payment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "client", "practice", "amount", "status", "due_date", "paid_at")
    list_filter = ("practice", "status", "due_date")
    search_fields = ("invoice_number", "client__first_name", "client__last_name", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("client", "invoice", "practice", "amount", "method", "paid_at")
    list_filter = ("practice", "method", "paid_at")
    search_fields = ("client__first_name", "client__last_name", "invoice__invoice_number", "external_payment_id")
    readonly_fields = ("created_at",)
