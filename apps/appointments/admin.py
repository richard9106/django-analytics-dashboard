from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "therapist",
        "practice",
        "starts_at",
        "ends_at",
        "status",
        "appointment_type",
        "sync_enabled",
        "sync_status",
    )
    list_filter = (
        "practice",
        "therapist",
        "status",
        "appointment_type",
        "sync_enabled",
        "sync_status",
        "starts_at",
    )
    search_fields = (
        "client__first_name",
        "client__last_name",
        "therapist__user__username",
        "therapist__user__first_name",
        "therapist__user__last_name",
        "practice__name",
        "external_event_id",
    )
    readonly_fields = ("created_at", "updated_at", "last_synced_at")
