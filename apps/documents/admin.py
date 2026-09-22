from django.contrib import admin

from .models import ClientDocument


@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "practice", "document_type", "uploaded_by", "created_at")
    list_filter = ("practice", "document_type", "created_at")
    search_fields = ("title", "client__first_name", "client__last_name", "practice__name")
    readonly_fields = ("created_at",)
