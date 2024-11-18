import random
import datetime
import os
import base64
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout
from django.contrib import messages
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from .forms import LoginForm, RegisterForm, LectureForm, TaskForm, EditTaskForm, TestCreateForm
from .decorators import not_logged_in_required, logged_in_required, user_not_teacher, user_not_admin
from django.contrib.auth.decorators import login_required
from .models import User, Contest, Lecture, Task, Test, TestGroup
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum

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
    

@method_decorator(login_required, name='dispatch')
class add_lecture_view(View):
    def get(self, request):
        form = LectureForm()
        return render(request, 'add_lecture.html', {'form': form})

    def post(self, request):
        form = LectureForm(request.POST, request.FILES)
        
        if form.is_valid():
            name = form.cleaned_data['name']
            is_public = form.cleaned_data['is_public']
            file = form.cleaned_data['file']
            
            # Walidacja typu pliku
            if not file.name.endswith('.pdf'):
                messages.error(request, "Plik musi być w formacie .pdf.")
                return redirect('add_lecture')
            
            # Generowanie unikalnej nazwy folderu
            username = request.user.username
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S%f')
            random_digits = random.randint(1000, 9999)
            folder_name = f"{name}_{username}_{timestamp}_{random_digits}"
            folder_path = os.path.join(settings.MEDIA_ROOT, 'lectures', folder_name)
            
            # Tworzenie folderu, jeśli nie istnieje
            os.makedirs(folder_path, exist_ok=True)
            
            # Zapis pliku
            file_path = os.path.join(folder_path, file.name)
            path_on_server = os.path.join('lectures', folder_name, file.name)
            with default_storage.open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # Zapis do bazy danych
            lecture = Lecture.objects.create(
                name=name,
                teacher=request.user,
                content_path=path_on_server,
                is_public=is_public
            )
            messages.success(request, "Wykład został dodany pomyślnie.")
            return redirect('/lecture_manager')
        
        messages.error(request, "Wystąpił błąd. Proszę sprawdzić poprawność formularza.")
        return render(request, 'add_lecture.html', {'form': form})
    

def pdf_page(request, pdf_path):
    pdf_path = os.path.join(settings.MEDIA_ROOT, pdf_path)
    with open(pdf_path, 'rb') as pdf_file:
        pdf_content = base64.b64encode(pdf_file.read()).decode()

    context = {
        "pdf": pdf_content,
    }

    return render(request, "pdf_page.html", context)


@method_decorator(login_required, name='dispatch')
class add_task_view(View):
    def get(self, request):
        form = TaskForm()
        return render(request, 'add_task.html', {'form': form})

    def post(self, request):
        form = TaskForm(request.POST, request.FILES)

        print("POST TASK!")
        
        if form.is_valid():
            name = form.cleaned_data['name']
            special_id = form.cleaned_data['special_id']
            time_limit = form.cleaned_data['time_limit']
            memory_limit = form.cleaned_data['memory_limit']
            is_public = form.cleaned_data['is_public']
            file = form.cleaned_data['file']

            print("Walidacja id!")
            
            # Walidacja unikalności special_id
            if Task.objects.filter(special_id=special_id).exists():
                messages.error(request, "Identyfikator jest już zajęty.")
                return redirect('add_task')
            
            print("Walidacja pliku!")
            
            # Walidacja typu pliku
            if not file.name.endswith('.pdf'):
                messages.error(request, "Plik musi być w formacie .pdf.")
                return redirect('add_task')
            
            print("Generowanie folderu docelowego")
            
            # Generowanie unikalnej nazwy folderu
            username = request.user.username
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S%f')
            random_digits = random.randint(1000, 9999)
            folder_name = f"{name}_{username}_{timestamp}_{random_digits}"
            folder_path = os.path.join(settings.MEDIA_ROOT, 'tasks', folder_name)

            print("Tworzenie folderu tests")
            
            # Tworzenie folderów
            os.makedirs(os.path.join(folder_path, 'tests'), exist_ok=True)

            print("Zapis pliku")
            
            # Zapis pliku
            file_path = os.path.join(folder_path, file.name)
            path_on_server = os.path.join('tasks', folder_name, file.name)
            with default_storage.open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            print("Zapis rekordu")
            
            # Zapis do bazy danych
            task = Task.objects.create(
                name=name,
                special_id=special_id,
                author=request.user,
                content_path=folder_path,
                pdf_file=path_on_server,
                time_limit=time_limit,
                memory_limit=memory_limit,
                is_public=is_public,
            )

            print("SUCCESS")

            messages.success(request, "Zadanie zostało dodane pomyślnie.")
            return redirect('/task_manager')
        
        messages.error(request, "Wystąpił błąd. Proszę sprawdzić poprawność formularza.")
        return render(request, 'add_task.html', {'form': form})
    

def edit_task_view(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    tests = Test.objects.filter(task=task)
    test_groups = TestGroup.objects.filter(task=task)

    if request.method == 'POST':
        form = EditTaskForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            new_file = form.cleaned_data.get('file')
            if new_file:
                # Usuń stary plik
                if task.pdf_file:
                    default_storage.delete(task.pdf_file)
                # Zapisz nowy plik
                folder_name = os.path.basename(task.content_path)
                folder_path = os.path.join(settings.MEDIA_ROOT, 'tasks', folder_name)
                file_path = os.path.join(folder_path, new_file.name)
                path_on_server = os.path.join('tasks', folder_name, new_file.name)

                with default_storage.open(file_path, 'wb+') as destination:
                    for chunk in new_file.chunks():
                        destination.write(chunk)

                task.pdf_file = path_on_server
            form.save()
            messages.success(request, "Poprawnie zmodyfikowano zadanie!")
            return redirect('edit_task', task_id=task.id)
        else:
            messages.error(request, "Wystąpił błąd podczas zapisywania formularza.")
    else:
        form = EditTaskForm(instance=task)

    return render(request, 'edit_task.html', {
        'task': task,
        'form': form,
        'tests': tests,
        'test_groups': test_groups,
    })

@csrf_exempt
def create_group_view(request, task_id):
    if request.method == 'POST':
        task = Task.objects.get(id=task_id)
        try:
            data = json.loads(request.body)
            name = data.get('name')
            points = int(data.get('points'))

            # Walidacja sumy punktów
            total_points = TestGroup.objects.filter(task=task).aggregate(Sum('points'))['points__sum'] or 0
            if total_points + points > 100:
                return JsonResponse({'status': 'error', 'message': 'Suma punktów dla wszystkich grup nie może przekraczać 100.'}, status=400)

            # Tworzenie nowej grupy
            new_group = TestGroup.objects.create(task=task, name=name, points=points)
            return JsonResponse({
                'status': 'success',
                'group': {
                    'id': new_group.id,
                    'name': new_group.name,
                    'points': new_group.points,
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
def update_group_view(request, group_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            points = data.get('points')

            group = TestGroup.objects.get(id=group_id)
            group.points = points
            group.save()

            return JsonResponse({'status': 'success'})
        except TestGroup.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Grupa nie istnieje.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
def create_test_view(request):
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        task = Task.objects.get(id=task_id)

        form = TestCreateForm(request.POST, request.FILES, task=task)

        if form.is_valid():
            # Tworzenie katalogu na testy
            name = form.cleaned_data['name']
            in_file = form.cleaned_data['in_file']
            out_file = form.cleaned_data['out_file']
            group = form.cleaned_data['group']

            tests_dir = os.path.join(task.content_path, 'tests', name)
            os.makedirs(tests_dir, exist_ok=True)

            # Zapis plików na serwerze
            in_file_path = os.path.join(tests_dir, in_file.name)
            out_file_path = os.path.join(tests_dir, out_file.name)

            with open(in_file_path, 'wb+') as f:
                for chunk in in_file.chunks():
                    f.write(chunk)

            with open(out_file_path, 'wb+') as f:
                for chunk in out_file.chunks():
                    f.write(chunk)

            # Tworzenie rekordu w bazie
            Test.objects.create(
                task=task,
                name=name,
                group=group,
                in_file=in_file.name,
                out_file=out_file.name,
            )

            return JsonResponse({'status': 'success', 'message': 'Nowy test został dodany.'})
        else:
            return JsonResponse({'status': 'error', 'message': form.errors.as_json()}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
def edit_test_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            test_id = data.get('test_id')
            group_id = data.get('group_id')

            test = Test.objects.get(id=test_id)
            if group_id:
                group = TestGroup.objects.get(id=group_id)
                test.group = group
            else:
                test.group = None

            test.save()
            return JsonResponse({'status': 'success', 'message': 'Grupa testu została zmodyfikowana.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)