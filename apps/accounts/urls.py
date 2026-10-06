from django.urls import path

from .views import PracticeDataExportView, PracticeSignupView, ProfileSettingsView, TeamManagementView, TeamMemberActionView


from .security_views import (MFASetupView, MFAChallengeView, RecoveryCodesView,
                             ReauthenticateView, SecuritySettingsView, SecuritySessionView)

urlpatterns = [
    path('security/', SecuritySettingsView.as_view(), name='security_settings'),
    path('security/setup/', MFASetupView.as_view(), name='mfa_setup'),
    path('security/challenge/', MFAChallengeView.as_view(), name='mfa_challenge'),
    path('security/codes/', RecoveryCodesView.as_view(), name='mfa_recovery_codes'),
    path('security/reauthenticate/', ReauthenticateView.as_view(), name='security_reauthenticate'),
    path('security/session/', SecuritySessionView.as_view(), name='security_session'),
    path("signup/", PracticeSignupView.as_view(), name="signup"),
    path("profile/", ProfileSettingsView.as_view(), name="profile_settings"),
    path("export/", PracticeDataExportView.as_view(), name="practice_data_export"),
    path("team/", TeamManagementView.as_view(), name="team_management"),
    path("team/<int:pk>/action/", TeamMemberActionView.as_view(), name="team_member_action"),
]
