from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from .access import is_client_user
from .forms import PracticeSignupForm


class RoleAwareLoginView(LoginView):
    template_name = "dashboard/login.html"

    def get_success_url(self):
        if is_client_user(self.request.user):
            return reverse_lazy("portal:dashboard")
        return super().get_success_url()


class PracticeSignupView(FormView):
    form_class = PracticeSignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from django.shortcuts import redirect

            if is_client_user(request.user):
                return redirect("portal:dashboard")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
