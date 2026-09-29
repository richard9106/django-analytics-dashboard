from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.crypto import get_random_string

from apps.accounts.models import UserProfile
from apps.practices.models import Practice, TherapistProfile


class PracticeSignupForm(forms.Form):
    practice_name = forms.CharField(max_length=140)
    practice_type = forms.ChoiceField(choices=Practice.PracticeType.choices)
    practice_email = forms.EmailField(required=False)
    practice_phone = forms.CharField(max_length=20, required=False)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    license_number = forms.CharField(max_length=60)
    license_state = forms.CharField(max_length=60)
    specialty = forms.CharField(max_length=140, required=False)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def build_username(self):
        User = get_user_model()
        base = self.cleaned_data["email"].split("@", 1)[0].strip().lower() or "user"
        base = "".join(char for char in base if char.isalnum() or char in "._+-")[:140] or "user"
        username = base
        counter = 2
        while User.objects.filter(username__iexact=username).exists():
            suffix = f"-{counter}"
            username = f"{base[:150 - len(suffix)]}{suffix}"
            counter += 1
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        license_number = cleaned_data.get("license_number")
        license_state = cleaned_data.get("license_state")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")

        if password1:
            try:
                validate_password(password1)
            except ValidationError as error:
                self.add_error("password1", error)

        if license_number and license_state and TherapistProfile.objects.filter(
            license_number__iexact=license_number,
            license_state__iexact=license_state,
        ).exists():
            self.add_error("license_number", "A therapist profile with this license already exists in that state.")

        return cleaned_data

    @transaction.atomic
    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.build_username(),
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )
        practice = Practice.objects.create(
            name=self.cleaned_data["practice_name"],
            practice_type=self.cleaned_data["practice_type"],
            email=self.cleaned_data.get("practice_email", ""),
            phone=self.cleaned_data.get("practice_phone", ""),
        )
        TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number=self.cleaned_data["license_number"],
            license_state=self.cleaned_data["license_state"],
            specialty=self.cleaned_data.get("specialty", ""),
        )
        UserProfile.objects.create(
            user=user,
            practice=practice,
            role=UserProfile.Role.OWNER,
            phone=self.cleaned_data.get("practice_phone", ""),
        )
        return user


class ForcePasswordChangeForm(SetPasswordForm):
    pass


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    error_messages = {
        "invalid_login": "Please enter a correct email and password.",
        "inactive": "This account is inactive.",
    }

    def clean(self):
        email = self.cleaned_data.get("username")
        if email:
            user = get_user_model().objects.filter(email__iexact=email).first()
            if user:
                self.cleaned_data["username"] = user.get_username()
        return super().clean()


class TeamMemberCreateForm(forms.Form):
    role = forms.ChoiceField(choices=(
        (UserProfile.Role.THERAPIST, "Therapist"),
        (UserProfile.Role.ADMIN, "Practice Admin"),
    ))
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    license_number = forms.CharField(max_length=60, required=False)
    license_state = forms.CharField(max_length=60, required=False)
    specialty = forms.CharField(max_length=140, required=False)
    send_invitation_email = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.temporary_password = ""

    def build_username(self):
        User = get_user_model()
        base = self.cleaned_data["email"].split("@", 1)[0].strip().lower() or "user"
        base = "".join(char for char in base if char.isalnum() or char in "._+-")[:140] or "user"
        username = base
        counter = 2
        while User.objects.filter(username__iexact=username).exists():
            suffix = f"-{counter}"
            username = f"{base[:150 - len(suffix)]}{suffix}"
            counter += 1
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        license_number = cleaned_data.get("license_number")
        license_state = cleaned_data.get("license_state")

        if role == UserProfile.Role.THERAPIST:
            if not license_number:
                self.add_error("license_number", "Therapists need a license number.")
            if not license_state:
                self.add_error("license_state", "Therapists need a license state.")
            if license_number and license_state and TherapistProfile.objects.filter(
                license_number__iexact=license_number,
                license_state__iexact=license_state,
            ).exists():
                self.add_error("license_number", "A therapist profile with this license already exists in that state.")

        if self.practice:
            subscription = getattr(self.practice, "subscription", None)
            if subscription and not subscription.can_add_internal_user():
                self.add_error("role", f"Your {subscription.get_plan_display()} plan has no internal user seats available.")
        return cleaned_data

    @transaction.atomic
    def save(self):
        User = get_user_model()
        self.temporary_password = get_random_string(14)
        user = User.objects.create_user(
            username=self.build_username(),
            email=self.cleaned_data["email"],
            password=self.temporary_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )
        if self.cleaned_data["role"] == UserProfile.Role.THERAPIST:
            TherapistProfile.objects.create(
                user=user,
                practice=self.practice,
                license_number=self.cleaned_data["license_number"],
                license_state=self.cleaned_data["license_state"],
                specialty=self.cleaned_data.get("specialty", ""),
            )
        profile = UserProfile(
            user=user,
            practice=self.practice,
            role=self.cleaned_data["role"],
            phone=self.cleaned_data.get("phone", ""),
            must_change_password=True,
        )
        profile.full_clean()
        profile.save()
        return user


class ProfileDetailsForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user and not self.is_bound:
            self.initial.update({
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': getattr(user.nuvia_profile, 'phone', ''),
            })

    def clean_email(self):
        email = self.cleaned_data['email']
        if get_user_model().objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def save(self):
        user = self.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.save(update_fields=['first_name', 'last_name', 'email'])
        profile = user.nuvia_profile
        profile.phone = self.cleaned_data['phone']
        profile.save(update_fields=['phone', 'updated_at'])
        return user
