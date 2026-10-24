from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .services import rate_limit
from django.core.exceptions import ValidationError


class SignupForm(UserCreationForm):
    email = forms.EmailField(max_length=150, label='ایمیل', widget=forms.EmailInput(attrs={'dir': 'ltr', 'autocomplete': 'email'}))
    first_name = forms.CharField(max_length=80, label='نام شما')

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if get_user_model().objects.filter(username=email).exists():
            raise forms.ValidationError('حسابی با این ایمیل وجود دارد.')
        return email

    def save(self, commit=True):
        self.instance.username = self.cleaned_data['email']
        return super().save(commit)


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150, label='نام کاربری یا ایمیل', widget=forms.TextInput(attrs={'dir': 'ltr', 'autocomplete': 'username'}))

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

    def clean(self):
        try:
            rate_limit(f'login:{self.request.META.get("REMOTE_ADDR", "unknown")}', 20, 300)
        except ValidationError as error:
            raise forms.ValidationError(error.messages)
        return super().clean()
