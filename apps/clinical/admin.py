from django.contrib import admin

from .models import SessionNote


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "therapist",
        "practice",
        "appointment",
        "note_type",
        "is_locked",
        "created_at",
    )
    list_filter = ("practice", "therapist", "note_type", "is_locked", "created_at")
    search_fields = (
        "client__first_name",
        "client__last_name",
        "therapist__user__username",
        "therapist__user__first_name",
        "therapist__user__last_name",
        "practice__name",
    )
    readonly_fields = ("created_at", "updated_at", "locked_at")
