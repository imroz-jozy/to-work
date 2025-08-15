# core/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile

PARTNER_CODE = "325237"  # Set your actual secret code here

class CustomSignupForm(UserCreationForm):
    # SQL Info
    sql_host = forms.CharField()
    sql_port = forms.CharField(required=False)
    sql_username = forms.CharField()
    sql_password = forms.CharField(widget=forms.PasswordInput)
    sql_database = forms.CharField()

    # Company Info
    company_name = forms.CharField()
    company_code = forms.CharField()

    # Partner Code
    partner_code = forms.CharField(help_text="Enter your partner code to register")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_partner_code(self):
        code = self.cleaned_data.get("partner_code")
        if code != PARTNER_CODE:
            raise forms.ValidationError("Invalid partner code")
        return code

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile = UserProfile.objects.create(
            user=user,
            sql_host=self.cleaned_data["sql_host"],
            sql_port=self.cleaned_data["sql_port"],
            sql_username=self.cleaned_data["sql_username"],
            sql_password=self.cleaned_data["sql_password"],
            sql_database=self.cleaned_data["sql_database"],
            company_name=self.cleaned_data["company_name"],
            company_address=self.cleaned_data["company_address"],
        )
        return user
