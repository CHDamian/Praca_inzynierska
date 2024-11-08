from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout
from django.contrib import messages
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from .forms import LoginForm, RegisterForm
from .decorators import not_logged_in_required, logged_in_required, user_not_teacher, user_not_admin
from django.contrib.auth.decorators import login_required
from .models import User, Contest, Lecture, Task

@not_logged_in_required
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            auth_login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Błąd logowania. Sprawdź poprawność danych.")
    else:
        form = LoginForm()
    return render(request, "login.html", {"form": form})

@logged_in_required
def logout_view(request):
    logout(request)
    messages.success(request, "Wylogowano pomyślnie!")
    return redirect('login')

@logged_in_required
def home_view(request):
    return render(request, 'home.html', {'first_name': request.user.first_name, 'last_name': request.user.last_name})


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']

            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='student'
            )
            auth_login(request, user)
            messages.success(request, "Rejestracja zakończona sukcesem.")
            return redirect('home')
        else:
            for field in form:
                for error in field.errors:
                    messages.error(request, f"{field.label}: {error}")
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


@method_decorator(login_required, name='dispatch')
class contest_manager_view(ListView):
    model = Contest
    template_name = 'contest_manager.html'
    context_object_name = 'contests'
    paginate_by = 10

    def get_queryset(self):
        # Pobierz aktualnego użytkownika
        user = self.request.user
        # Odbierz zapytanie wyszukiwania, sortowania
        search_query = self.request.GET.get('search', '')
        sort_option = self.request.GET.get('sort', 'name')
        sort_reverse = self.request.GET.get('reverse', 'false') == 'true'

        # Filtrowanie w zależności od roli
        queryset = Contest.objects.all() if user.role == 'admin' else Contest.objects.filter(teacher=user)

        # Wyszukiwanie po nazwie
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        # Sortowanie
        if sort_option in ['name', 'teacher', 'start_date', 'end_date']:
            if sort_option == 'teacher':
                queryset = queryset.order_by(f"{'-' if sort_reverse else ''}teacher__first_name")
            else:
                queryset = queryset.order_by(f"{'-' if sort_reverse else ''}{sort_option}")

        return queryset
    
@method_decorator(login_required, name='dispatch')
class lecture_manager_view(ListView):
    model = Lecture
    template_name = 'lecture_manager.html'
    context_object_name = 'lectures'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        search_query = self.request.GET.get('search', '')
        sort_option = self.request.GET.get('sort', 'name')
        sort_reverse = self.request.GET.get('reverse', 'false') == 'true'
        
        # Retrieve lectures based on user's role
        if user.role == 'admin':
            queryset = Lecture.objects.all()
        else:
            queryset = Lecture.objects.filter(models.Q(teacher=user) | models.Q(is_public=True))

        # Search functionality
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        # Sorting functionality
        if sort_option in ['name', 'teacher']:
            if sort_option == 'teacher':
                queryset = queryset.order_by(f"{'-' if sort_reverse else ''}teacher__first_name")
            else:
                queryset = queryset.order_by(f"{'-' if sort_reverse else ''}{sort_option}")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sort_reverse'] = self.request.GET.get('reverse', 'false')
        context['search_query'] = self.request.GET.get('search', '')
        return context
    

@method_decorator(login_required, name='dispatch')
class task_manager_view(ListView):
    model = Task
    template_name = 'task_manager.html'
    context_object_name = 'tasks'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        search_query = self.request.GET.get('search', '')
        sort_option = self.request.GET.get('sort', 'special_id')
        sort_reverse = self.request.GET.get('reverse', 'false') == 'true'

        # Filtrowanie zadań na podstawie roli użytkownika
        if user.role == 'admin':
            queryset = Task.objects.all()
        else:
            queryset = Task.objects.filter(author=user) | Task.objects.filter(is_public=True)

        # Wyszukiwanie po nazwie
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        # Sortowanie
        if sort_option in ['special_id', 'name', 'author']:
            if sort_option == 'author':
                queryset = queryset.order_by(f"{'-' if sort_reverse else ''}author__first_name")
            else:
                queryset = queryset.order_by(f"{'-' if sort_reverse else ''}{sort_option}")

        return queryset