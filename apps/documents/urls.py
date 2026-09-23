from django.urls import path

from .views import DocumentCreateView, DocumentDeleteView, DocumentDownloadView, DocumentListView

app_name = 'documents'

urlpatterns = [
    path('', DocumentListView.as_view(), name='list'),
    path('new/', DocumentCreateView.as_view(), name='create'),
    path('<int:pk>/download/', DocumentDownloadView.as_view(), name='download'),
    path('<int:pk>/delete/', DocumentDeleteView.as_view(), name='delete'),
]
