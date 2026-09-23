from django.contrib import admin

from .models import InsurancePayer, InsuranceRate, Invoice, PackageUsage, Payment, ServicePackage, SessionPackageTemplate


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "client", "practice", "amount", "status", "package", "due_date", "paid_at")
    list_filter = ("practice", "status", "due_date")
    search_fields = ("invoice_number", "client__first_name", "client__last_name", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("client", "invoice", "practice", "amount", "method", "paid_at")
    list_filter = ("practice", "method", "paid_at")
    search_fields = ("client__first_name", "client__last_name", "invoice__invoice_number", "external_payment_id")
    readonly_fields = ("created_at",)


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "practice", "template", "sessions_purchased", "sessions_used", "total_price", "status")
    list_filter = ("practice", "status", "purchased_at", "expires_at")
    search_fields = ("name", "client__first_name", "client__last_name", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PackageUsage)
class PackageUsageAdmin(admin.ModelAdmin):
    list_display = ("package", "appointment", "quantity", "used_at")
    list_filter = ("package__practice", "used_at")
    search_fields = ("package__name", "package__client__first_name", "package__client__last_name")
    readonly_fields = ("created_at",)


@admin.register(SessionPackageTemplate)
class SessionPackageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "practice", "sessions_included", "price", "active")
    list_filter = ("practice", "active")
    search_fields = ("name", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InsurancePayer)
class InsurancePayerAdmin(admin.ModelAdmin):
    list_display = ("name", "practice", "payer_id", "is_system_template", "active")
    list_filter = ("practice", "is_system_template", "active")
    search_fields = ("name", "payer_id", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InsuranceRate)
class InsuranceRateAdmin(admin.ModelAdmin):
    list_display = ("payer", "practice", "state", "service_code", "reimbursement_amount", "active")
    list_filter = ("practice", "state", "service_code", "active")
    search_fields = ("payer__name", "state", "service_code", "service_label")
    readonly_fields = ("created_at", "updated_at")
