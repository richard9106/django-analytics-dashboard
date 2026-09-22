from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from .forms import PracticeSignupForm


class PracticeSignupView(FormView):
    form_class = PracticeSignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from django.shortcuts import redirect

            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
