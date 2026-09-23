from django.urls import path

from .views import (
    PortalAccessCreateView,
    PortalAccessDeleteView,
    PortalAccessListView,
    PortalAccessPasswordResetView,
    PortalAccessUpdateView,
)

app_name = 'portal_settings'

urlpatterns = [
    path('client-portal/', PortalAccessListView.as_view(), name='portal_access'),
    path('client-portal/new/', PortalAccessCreateView.as_view(), name='portal_access_create'),
    path('client-portal/<int:pk>/edit/', PortalAccessUpdateView.as_view(), name='portal_access_edit'),
    path('client-portal/<int:pk>/reset-password/', PortalAccessPasswordResetView.as_view(), name='portal_access_reset_password'),
    path('client-portal/<int:pk>/delete/', PortalAccessDeleteView.as_view(), name='portal_access_delete'),
]
