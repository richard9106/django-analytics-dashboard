from django.urls import path

from .views import PracticeSignupView


urlpatterns = [
    path("signup/", PracticeSignupView.as_view(), name="signup"),
]
