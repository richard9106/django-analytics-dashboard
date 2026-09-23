from django_summernote.admin import SummernoteModelAdmin
from django.contrib import admin

from .models import ExternalIntegration, Practice, TherapistProfile


class PracticeAdmin(SummernoteModelAdmin):
    """Admin class for Practice model."""

    list_display = ("name", "practice_type", "phone", "email", "city", "state")
    search_fields = ("name", "practice_type", "phone", "email", "city", "state")


class TherapistProfileAdmin(SummernoteModelAdmin):
    """Admin class for TherapistProfile model."""

    list_display = (
        "user",
        "practice",
        "license_number",
        "license_state",
        "specialty")
    search_fields = (
        "user__username",
        "practice__name",
        "license_number",
        "license_state",
        "specialty",
    )


admin.site.register(Practice, PracticeAdmin)
admin.site.register(TherapistProfile, TherapistProfileAdmin)


@admin.register(ExternalIntegration)
class ExternalIntegrationAdmin(admin.ModelAdmin):
    list_display = ("practice", "provider", "status", "account_email", "send_email_enabled", "read_email_enabled", "file_storage_enabled")
    list_filter = ("practice", "provider", "status")
    search_fields = ("practice__name", "account_email", "default_folder")
    readonly_fields = ("created_at", "updated_at", "connected_at")
