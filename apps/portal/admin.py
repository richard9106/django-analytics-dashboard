from django.contrib import admin

from .models import ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate


@admin.register(ClientPortalAccess)
class ClientPortalAccessAdmin(admin.ModelAdmin):
    list_display = ("client", "user", "practice", "is_active", "invited_at", "accepted_at")
    list_filter = ("practice", "is_active")
    search_fields = ("client__first_name", "client__last_name", "user__username", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClientPortalRequest)
class ClientPortalRequestAdmin(admin.ModelAdmin):
    list_display = ("subject", "category", "status", "client", "practice", "created_at")
    list_filter = ("practice", "category", "status", "created_at")
    search_fields = ("subject", "message", "client__first_name", "client__last_name", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(IntakePacketTemplate)
class IntakePacketTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "practice", "active", "created_at")
    list_filter = ("practice", "active")
    search_fields = ("name", "description", "practice__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClientIntakeAssignment)
class ClientIntakeAssignmentAdmin(admin.ModelAdmin):
    list_display = ("template", "client", "practice", "status", "submitted_at", "reviewed_at")
    list_filter = ("practice", "status", "created_at")
    search_fields = ("template__name", "client__first_name", "client__last_name", "practice__name")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "reviewed_at")
