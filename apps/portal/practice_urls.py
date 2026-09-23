from django.urls import path

from .views import PracticePortalRequestListView, PracticePortalRequestStatusView

app_name = 'portal_requests'

urlpatterns = [
    path('', PracticePortalRequestListView.as_view(), name='list'),
    path('<int:pk>/status/', PracticePortalRequestStatusView.as_view(), name='status'),
]
