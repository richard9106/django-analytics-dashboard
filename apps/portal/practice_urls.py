from django.urls import path

from .views import PracticeConversationDetailView, PracticeConversationListView, PracticePortalRequestListView, PracticePortalRequestStatusView, PublicBookingRequestApproveView, PublicBookingRequestDeclineView

app_name = 'portal_requests'

urlpatterns = [
    path('', PracticePortalRequestListView.as_view(), name='list'),
    path('<int:pk>/status/', PracticePortalRequestStatusView.as_view(), name='status'),
    path('messages/', PracticeConversationListView.as_view(), name='conversations'),
    path('messages/<uuid:public_id>/', PracticeConversationDetailView.as_view(), name='conversation_detail'),
    path('booking/<int:pk>/approve/', PublicBookingRequestApproveView.as_view(), name='booking_approve'),
    path('booking/<int:pk>/decline/', PublicBookingRequestDeclineView.as_view(), name='booking_decline'),
]
