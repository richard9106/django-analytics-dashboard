from django.urls import path

from .views import (
    DropboxIntegrationUpdateView,
    GoogleOAuthCallbackView,
    GoogleOAuthConnectView,
    GoogleOAuthDisconnectView,
    IntegrationSettingsView,
)

app_name = 'practice_settings'

urlpatterns = [
    path('integrations/', IntegrationSettingsView.as_view(), name='integrations'),
    path('integrations/google/connect/', GoogleOAuthConnectView.as_view(), name='google_connect'),
    path('integrations/google/callback/', GoogleOAuthCallbackView.as_view(), name='google_callback'),
    path('integrations/google/disconnect/', GoogleOAuthDisconnectView.as_view(), name='google_disconnect'),
    path('integrations/dropbox/', DropboxIntegrationUpdateView.as_view(), name='dropbox_update'),
]
