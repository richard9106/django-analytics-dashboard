from django_summernote.admin import SummernoteModelAdmin
from django.contrib import admin

from .models import Practice, TherapistProfile


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
# Register your models here.
