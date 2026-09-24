from django.urls import path

from .views import ClientIntakeAssignView, ClientIntakeReviewView, IntakeTemplateCreateView, PracticeIntakeListView

app_name = 'intake'

urlpatterns = [
    path('', PracticeIntakeListView.as_view(), name='list'),
    path('templates/new/', IntakeTemplateCreateView.as_view(), name='template_create'),
    path('assign/', ClientIntakeAssignView.as_view(), name='assign'),
    path('<int:pk>/review/', ClientIntakeReviewView.as_view(), name='review'),
]
