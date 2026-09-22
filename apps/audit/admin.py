from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "object_type", "object_id", "practice", "actor", "created_at")
    list_filter = ("practice", "action", "object_type", "created_at")
    search_fields = ("object_type", "object_id", "actor__username", "practice__name")
    readonly_fields = ("created_at",)
