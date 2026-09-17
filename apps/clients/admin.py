from django_summernote.admin import SummernoteModelAdmin
from django.contrib import admin

from .models import Client


class ClientAdmin(SummernoteModelAdmin):
    """Admin class for Client model."""

    list_display = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "primary_therapist",
        "status",
        "created_at",
        "updated_at"
    )
    list_filter = ("practice", "primary_therapist", "status")
    search_fields = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "practice__name",
        "primary_therapist",
        "primary_therapist__user__first_name",
        "primary_therapist__user__last_name",
        "primary_therapist__user__username",
        "ensurance_provider",
        "ensurance_member_id",
        "emergyency_contact_name",
        "emergyency_contact_phone",
    )


admin.site.register(Client, ClientAdmin)
