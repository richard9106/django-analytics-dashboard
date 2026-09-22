from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("subject", "practice", "channel", "status", "recipient_user", "client", "created_at")
    list_filter = ("practice", "channel", "status", "created_at")
    search_fields = ("subject", "recipient_user__username", "client__first_name", "client__last_name")
    readonly_fields = ("created_at",)
