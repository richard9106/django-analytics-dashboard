from django.urls import path

from .views import DocumentCreateView, DocumentDeleteView, DocumentDownloadView, DocumentGoogleDriveExportView, DocumentListView

app_name = 'documents'

urlpatterns = [
    path('', DocumentListView.as_view(), name='list'),
    path('new/', DocumentCreateView.as_view(), name='create'),
    path('<int:pk>/download/', DocumentDownloadView.as_view(), name='download'),
    path('<int:pk>/export/google-drive/', DocumentGoogleDriveExportView.as_view(), name='google_drive_export'),
    path('<int:pk>/delete/', DocumentDeleteView.as_view(), name='delete'),
]
