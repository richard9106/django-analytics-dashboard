from django.urls import path

from .views import SessionNoteCreateView, SessionNoteDeleteView, SessionNoteListView, SessionNoteUpdateView

app_name = 'clinical'

urlpatterns = [
    path('', SessionNoteListView.as_view(), name='list'),
    path('new/', SessionNoteCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', SessionNoteUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', SessionNoteDeleteView.as_view(), name='delete'),
]
