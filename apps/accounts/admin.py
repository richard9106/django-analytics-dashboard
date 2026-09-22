from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "practice", "role", "phone", "created_at")
    list_filter = ("practice", "role")
    search_fields = ("user__username", "user__first_name", "user__last_name", "practice__name")
