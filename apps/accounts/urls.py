from django.urls import path

from .views import PracticeSignupView, ProfileSettingsView, TeamManagementView


urlpatterns = [
    path("signup/", PracticeSignupView.as_view(), name="signup"),
    path("profile/", ProfileSettingsView.as_view(), name="profile_settings"),
    path("team/", TeamManagementView.as_view(), name="team_management"),
]
