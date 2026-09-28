from django.urls import path

from .views import PracticePortalRequestListView, PracticePortalRequestStatusView, PublicBookingRequestApproveView, PublicBookingRequestDeclineView

app_name = 'portal_requests'

urlpatterns = [
    path('', PracticePortalRequestListView.as_view(), name='list'),
    path('<int:pk>/status/', PracticePortalRequestStatusView.as_view(), name='status'),
    path('booking/<int:pk>/approve/', PublicBookingRequestApproveView.as_view(), name='booking_approve'),
    path('booking/<int:pk>/decline/', PublicBookingRequestDeclineView.as_view(), name='booking_decline'),
]
