from django.contrib import admin

from .models import Diagnosis, SessionNote, TreatmentPlan


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "therapist",
        "practice",
        "appointment",
        "treatment_plan",
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


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ("client", "practice", "code", "label", "diagnosed_at", "active")
    list_filter = ("practice", "active", "diagnosed_at")
    search_fields = ("client__first_name", "client__last_name", "code", "label", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "therapist", "practice", "status", "start_date", "review_date")
    list_filter = ("practice", "status", "start_date", "review_date")
    search_fields = ("title", "client__first_name", "client__last_name", "therapist__user__username", "practice__name")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("diagnoses",)
