from django.contrib import admin
from django.core.exceptions import PermissionDenied

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

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_locked:
            return tuple(field.name for field in self.model._meta.fields)
        return super().get_readonly_fields(request, obj)

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.is_locked) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.is_locked) and super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(is_locked=True).exists():
            raise PermissionDenied('Locked clinical notes cannot be deleted.')
        super().delete_queryset(request, queryset)


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
