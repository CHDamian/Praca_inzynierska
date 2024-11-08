# forms.py
from django import forms
from django.contrib.auth import authenticate
import re

class LoginForm(forms.Form):
    username_or_email = forms.CharField(label="Nazwa użytkownika lub Email", max_length=254)
    password = forms.CharField(label="Hasło", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        username_or_email = cleaned_data.get("username_or_email")
        password = cleaned_data.get("password")

        # Autoryzacja użytkownika na podstawie nazwy lub emaila
        if username_or_email and password:
            user = authenticate(username=username_or_email, password=password) or \
                   authenticate(email=username_or_email, password=password)
            if not user:
                raise forms.ValidationError("Nieprawidłowa nazwa użytkownika/email lub hasło.")
            cleaned_data["user"] = user
        return cleaned_data
    

class RegisterForm(forms.Form):
    username = forms.CharField(
        label="Nazwa użytkownika",
        min_length=3,
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label="Hasło",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8,
        help_text="Hasło musi mieć co najmniej 8 znaków, zawierać jedną małą literę, jedną dużą, jedną cyfrę i jeden znak specjalny."
    )
    password_confirm = forms.CharField(
        label="Powtórz hasło",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        label="Imię/Imiona",
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label="Nazwisko",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'\d', password) or not re.search(r'\W', password):
            raise forms.ValidationError("Hasło musi zawierać małą literę, dużą literę, cyfrę i znak specjalny.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password != password_confirm:
            raise forms.ValidationError("Hasła się nie zgadzają.")
        return cleaned_data

