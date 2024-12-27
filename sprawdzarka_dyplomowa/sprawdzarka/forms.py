# forms.py
from django import forms
from django.contrib.auth import authenticate
from .models import Lecture, Task, TestGroup, Test, Contest, Solution
from django.core.exceptions import ValidationError
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

class LectureForm(forms.ModelForm):
    file = forms.FileField(required=True)  # Pole dla pliku .pdf
    
    class Meta:
        model = Lecture
        fields = ['name', 'is_public', 'file']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa wykładu'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }


class TaskForm(forms.ModelForm):
    file = forms.FileField(required=True)

    class Meta:
        model = Task
        fields = ['name', 'special_id', 'time_limit', 'memory_limit', 'is_public', 'file']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'minlength': 3}),
            'special_id': forms.TextInput(attrs={'class': 'form-control', 'minlength': 3}),
            'time_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'memory_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }


class EditTaskForm(forms.ModelForm):
    file = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Task
        fields = ['name', 'special_id', 'time_limit', 'memory_limit', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'minlength': 3}),
            'special_id': forms.TextInput(attrs={'class': 'form-control', 'minlength': 3}),
            'time_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'memory_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_special_id(self):
        special_id = self.cleaned_data.get('special_id')
        if Task.objects.filter(special_id=special_id).exclude(id=self.instance.id).exists():
            raise ValidationError("Identyfikator musi być unikalny.")
        return special_id
    

class CreateGroupForm(forms.ModelForm):
    class Meta:
        model = TestGroup
        fields = ['name', 'points']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa grupy'}),
            'points': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
        }


class TestCreateForm(forms.ModelForm):
    # Dodatkowe pola
    in_file = forms.FileField(
        label="Plik wejściowy (.in)",
        widget=forms.ClearableFileInput(attrs={'accept': '.in'}),
        required=True
    )
    out_file = forms.FileField(
        label="Plik wyjściowy (.out)",
        widget=forms.ClearableFileInput(attrs={'accept': '.out'}),
        required=True
    )
    group = forms.ModelChoiceField(
        label="Grupa",
        queryset=TestGroup.objects.all(),
        required=False,
        empty_label="Brak",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Test
        fields = ['name', 'group']

    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop('task', None)  # Zadanie przekazywane do formularza
        super().__init__(*args, **kwargs)
        if self.task:
            # Filtrujemy grupy związane z tym zadaniem
            self.fields['group'].queryset = TestGroup.objects.filter(task=self.task)

    def clean_name(self):
        """
        Sprawdzanie unikalności nazwy testu w obrębie zadania.
        """
        name = self.cleaned_data['name']
        if Test.objects.filter(task=self.task, name=name).exists():
            raise forms.ValidationError(f"Test o nazwie '{name}' już istnieje dla tego zadania.")
        return name

    def clean_in_file(self):
        """
        Sprawdzanie poprawności rozszerzenia pliku wejściowego.
        """
        in_file = self.cleaned_data['in_file']
        if not in_file.name.endswith('.in'):
            raise forms.ValidationError("Plik wejściowy musi mieć rozszerzenie .in")
        return in_file

    def clean_out_file(self):
        """
        Sprawdzanie poprawności rozszerzenia pliku wyjściowego.
        """
        out_file = self.cleaned_data['out_file']
        if not out_file.name.endswith('.out'):
            raise forms.ValidationError("Plik wyjściowy musi mieć rozszerzenie .out")
        return out_file
    
class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = ['name', 'start_date', 'end_date', 'send_limit', 'password']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa konkursu'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'send_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'password': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Hasło (opcjonalne)'}),
        }

class SendSolutionForm(forms.ModelForm):
    solution_file = forms.FileField(
        label="Rozwiązanie",
        required=True,
        widget=forms.ClearableFileInput(attrs={'accept': '.c,.cpp,.cc,.java,.cs'})
    )

    def __init__(self, *args, **kwargs):
        tasks = kwargs.pop('tasks', [])
        super().__init__(*args, **kwargs)
        self.fields['contest_task'].queryset = tasks
        self.fields['contest_task'].label = "Zadanie"
        self.fields['lang'].label = "Język"

    class Meta:
        model = Solution
        fields = ['contest_task', 'lang', 'solution_file']