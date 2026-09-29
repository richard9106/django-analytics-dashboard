from django import forms


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
