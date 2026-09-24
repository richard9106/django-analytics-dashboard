from django.urls import path

from .views import (
    DiagnosisCreateView,
    DiagnosisDeleteView,
    DiagnosisUpdateView,
    SessionNoteCreateView,
    SessionNoteDeleteView,
    SessionNoteListView,
    SessionNoteUpdateView,
    TreatmentPlanCreateView,
    TreatmentPlanCompleteReviewView,
    TreatmentPlanDeleteView,
    TreatmentPlanListView,
    TreatmentPlanUpdateView,
)

app_name = 'clinical'

urlpatterns = [
    path('', SessionNoteListView.as_view(), name='list'),
    path('treatment-plans/', TreatmentPlanListView.as_view(), name='treatment_plans'),
    path('treatment-plans/new/', TreatmentPlanCreateView.as_view(), name='treatment_plan_create'),
    path('treatment-plans/<int:pk>/complete-review/', TreatmentPlanCompleteReviewView.as_view(), name='treatment_plan_complete_review'),
    path('treatment-plans/<int:pk>/edit/', TreatmentPlanUpdateView.as_view(), name='treatment_plan_edit'),
    path('treatment-plans/<int:pk>/delete/', TreatmentPlanDeleteView.as_view(), name='treatment_plan_delete'),
    path('diagnoses/new/', DiagnosisCreateView.as_view(), name='diagnosis_create'),
    path('diagnoses/<int:pk>/edit/', DiagnosisUpdateView.as_view(), name='diagnosis_edit'),
    path('diagnoses/<int:pk>/delete/', DiagnosisDeleteView.as_view(), name='diagnosis_delete'),
    path('new/', SessionNoteCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', SessionNoteUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', SessionNoteDeleteView.as_view(), name='delete'),
]
