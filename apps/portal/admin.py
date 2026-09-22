from django.contrib import admin

from .models import ClientPortalAccess


@admin.register(ClientPortalAccess)
class ClientPortalAccessAdmin(admin.ModelAdmin):
    list_display = ("client", "user", "practice", "is_active", "invited_at", "accepted_at")
    list_filter = ("practice", "is_active")
    search_fields = ("client__first_name", "client__last_name", "user__username", "practice__name")
    readonly_fields = ("created_at", "updated_at")
