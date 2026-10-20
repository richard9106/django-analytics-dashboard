from django.urls import path

from .invitation_views import AccountInvitationView
from .views import PracticeDataExportView, PracticeSignupView, ProfileSettingsView, TeamManagementView, TeamMemberActionView


from .security_views import (MFASetupView, MFAChallengeView, RecoveryCodesView,
                             ReauthenticateView, SecuritySettingsView, SecuritySessionView)

from .email_security import EmailChallengeView

from .contract_views import ContractsView, ContractReviewView, ContractSignView, ContractDownloadView

urlpatterns = [
    path('contracts/', ContractsView.as_view(), name='clinical_contracts'),
    path('contracts/<uuid:pk>/', ContractReviewView.as_view(), name='clinical_contract_review'),
    path('contracts/<uuid:pk>/sign/', ContractSignView.as_view(), name='clinical_contract_sign'),
    path('contracts/<uuid:pk>/download/', ContractDownloadView.as_view(), name='clinical_contract_download'),
    path('security/email/', EmailChallengeView.as_view(), name='email_security_challenge'),
    path('invitations/<uidb64>/<token>/', AccountInvitationView.as_view(), name='account_invitation'),
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
