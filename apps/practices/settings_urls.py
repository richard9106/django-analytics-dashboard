from django.urls import path

from .views import IntegrationSettingsView, IntegrationUpdateView

app_name = 'practice_settings'

urlpatterns = [
    path('integrations/', IntegrationSettingsView.as_view(), name='integrations'),
    path('integrations/<str:provider>/', IntegrationUpdateView.as_view(), name='integration_update'),
]
