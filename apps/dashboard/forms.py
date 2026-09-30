from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import UserProfile
from .models import Task


class SupportContactForm(forms.Form):
    name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    topic = forms.ChoiceField(choices=(
        ('setup', 'Practice setup'),
        ('billing', 'Billing or payments'),
        ('integrations', 'Gmail, Google, or Stripe'),
        ('technical', 'Technical issue'),
        ('other', 'Other'),
    ))
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 6}), max_length=4000)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        value = self.cleaned_data['website']
        if value:
            raise forms.ValidationError('Unable to send this request.')
        return value


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'due_date', 'priority', 'status', 'assignee')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice_id = practice.pk if practice else None
        self.fields['assignee'].queryset = get_user_model().objects.filter(
            nuvia_profile__practice=practice,
        ).exclude(nuvia_profile__role=UserProfile.Role.CLIENT).order_by('first_name', 'username')
        self.fields['assignee'].label_from_instance = lambda user: user.get_full_name() or user.username

    def clean_assignee(self):
        assignee = self.cleaned_data['assignee']
        if assignee.nuvia_profile.practice_id != self.practice_id:
            raise forms.ValidationError('Choose a team member from this practice.')
        return assignee
