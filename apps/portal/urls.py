from django.urls import path

from .views import ClientPortalDashboardView, ClientPortalRequestCreateView

app_name = 'portal'

urlpatterns = [
    path('', ClientPortalDashboardView.as_view(), name='dashboard'),
    path('requests/new/', ClientPortalRequestCreateView.as_view(), name='request_create'),
]
