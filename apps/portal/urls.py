from django.urls import path

from .views import ClientPortalDashboardView

app_name = 'portal'

urlpatterns = [
    path('', ClientPortalDashboardView.as_view(), name='dashboard'),
]
