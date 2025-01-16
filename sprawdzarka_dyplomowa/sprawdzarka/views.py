import random
import datetime
import os
import base64
import json
import logging
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout
from django.contrib import messages
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from .forms import LoginForm, RegisterForm, LectureForm, TaskForm, EditTaskForm, TestCreateForm, ContestForm, SendSolutionForm, QuestionForm, AnswerForm, EditLectureForm
from .decorators import not_logged_in_required, logged_in_required, user_not_teacher, user_not_admin
from django.contrib.auth.decorators import login_required
from .models import User, Contest, Lecture, Task, Test, TestGroup, ContestLecture, ContestTask, ContestSigned, Solution, SolutionTestResult, Question
from django.db.models import Max
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.views import View
from django.http import JsonResponse, Http404, FileResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Q, Prefetch, Max, F, Count
from .tasks import execute_cpp, execute_java, execute_cs
from datetime import datetime
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.db import transaction
from django.core.serializers import serialize

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

@not_logged_in_required
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
    
    
@method_decorator(login_required, name='dispatch')
class edit_lecture_view(View):
    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id)

        # Check permissions
        if request.user != lecture.teacher and request.user.role != 'admin':
            return HttpResponseForbidden("You do not have permission to edit this lecture.")

        form = EditLectureForm(instance=lecture)
        return render(request, 'edit_lecture.html', {'form': form, 'lecture': lecture})

    def post(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id)

        # Check permissions
        if request.user != lecture.teacher and request.user.role != 'admin':
            return HttpResponseForbidden("You do not have permission to edit this lecture.")

        form = EditLectureForm(request.POST, request.FILES, instance=lecture)

        if form.is_valid():
            is_public = form.cleaned_data['is_public']
            file = request.FILES.get('file', None)

            # Handle file upload
            if file:
                if not file.name.endswith('.pdf'):
                    messages.error(request, "Plik musi być w formacie .pdf.")
                    return redirect('edit_lecture', lecture_id=lecture.id)

                # Remove old file if exists
                if lecture.content_path and default_storage.exists(os.path.join(settings.MEDIA_ROOT, lecture.content_path)):
                    default_storage.delete(os.path.join(settings.MEDIA_ROOT, lecture.content_path))

                # Save new file in the same directory
                old_folder_path = os.path.join(settings.MEDIA_ROOT, os.path.dirname(lecture.content_path))
                os.makedirs(old_folder_path, exist_ok=True)
                file_path = os.path.join(old_folder_path, file.name)
                path_on_server = os.path.relpath(file_path, settings.MEDIA_ROOT)

                with default_storage.open(file_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)

                lecture.content_path = path_on_server

            lecture.is_public = is_public
            lecture.save()

            messages.success(request, "Wykład został zaktualizowany pomyślnie.")
            return redirect('/lecture_manager')

        messages.error(request, "Wystąpił błąd. Proszę sprawdzić poprawność formularza.")
        return render(request, 'edit_lecture.html', {'form': form, 'lecture': lecture})


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
            new_test = Test.objects.create(
                task=task,
                name=name,
                group=group,
                in_file=in_file.name,
                out_file=out_file.name,
            )

            # Przygotowanie danych do odpowiedzi
            response_data = {
                'id': new_test.id,
                'name': new_test.name,
                'in_file_url': f"/media/{new_test.in_file}",
                'out_file_url': f"/media/{new_test.out_file}",
                'group_id': new_test.group.id if new_test.group else None,
                'group_name': new_test.group.name if new_test.group else 'Brak',
            }

            return JsonResponse({'status': 'success', 'test': response_data, 'message': 'Nowy test został dodany.'})
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


@method_decorator(login_required, name='dispatch')
class add_contest_view(View):
    def get(self, request):
        form = ContestForm()
        return render(request, 'add_contest.html', {'form': form})

    def post(self, request):
        form = ContestForm(request.POST)
        
        if form.is_valid():
            name = form.cleaned_data['name']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            send_limit = 10
            password = form.cleaned_data['password']
            
            if send_limit <= 0:
                messages.error(request, "Limit wysyłek musi być większy niż 0.")
                return render(request, 'add_contest.html', {'form': form})

            contest = Contest(
                name=name,
                teacher=request.user,
                start_date=start_date,
                end_date=end_date,
                send_limit=send_limit,
                password=password if password else None,
                frozen_ranking=None
            )
            contest.save()
            messages.success(request, "Konkurs został dodany pomyślnie.")
            return redirect('/contest_manager')
        
        messages.error(request, "Wystąpił błąd. Proszę sprawdzić poprawność formularza.")
        return render(request, 'add_contest.html', {'form': form})
    

@login_required
def edit_contest_view(request, contest_id):
    contest = get_object_or_404(Contest, id=contest_id)

    # Check permissions: user must be the owner (teacher) or an admin
    if request.user != contest.teacher and request.user.role != 'admin':
        return redirect('home')

    if request.method == 'POST':
        # Handle freezing/unfreezing ranking
        if 'freeze_ranking' in request.POST:
            contest.frozen_ranking = now()
            contest.save()
            messages.success(request, 'Ranking został zamrożony!')
            return redirect('edit_contest', contest_id=contest.id)

        elif 'unfreeze_ranking' in request.POST:
            contest.frozen_ranking = None
            contest.save()
            messages.success(request, 'Ranking został odmrożony!')
            return redirect('edit_contest', contest_id=contest.id)

        # Handle contest form submission
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pomyślnie zaktualizowano konkurs!')
            return redirect('edit_contest', contest_id=contest.id)
        else:
            messages.error(request, 'Wystąpił błąd podczas aktualizacji konkursu.')
    else:
        form = ContestForm(instance=contest)

    return render(request, 'edit_contest.html', {
        'contest': contest,
        'form': form,
    })

@method_decorator(login_required, name='dispatch')
class edit_contest_lectures_view(ListView):
    template_name = 'edit_contest_lectures.html'
    context_object_name = 'lectures'
    paginate_by = 10  # Liczba wykładów na stronie

    def get_queryset(self):
        contest_id = self.kwargs['contest_id']
        contest = get_object_or_404(Contest, id=contest_id)
        saved_lectures_ids = ContestLecture.objects.filter(contest=contest).values_list('lecture_id', flat=True)

        # Wszystkie dostępne wykłady (bez zapisanych)
        lectures = Lecture.objects.filter(
            (Q(teacher=self.request.user) | Q(is_public=True)) & ~Q(id__in=saved_lectures_ids)
        ).order_by('id')  # Dodano porządek

        return lectures


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contest_id = self.kwargs['contest_id']
        contest = get_object_or_404(Contest, id=contest_id)

        # Zapisane wykłady
        saved_lectures = ContestLecture.objects.filter(contest=contest).select_related('lecture')

        context.update({
            'contest': contest,
            'saved_lectures': saved_lectures,
        })
        return context
    

logger = logging.getLogger(__name__)

@csrf_exempt
def add_lecture_to_contest(request):
    if request.method == 'POST':
        try:
            logger.info(f"Request body: {request.body}")  # Loguj całe body żądania
            data = json.loads(request.body)
            contest_id = data.get('contest_id')
            lecture_id = data.get('lecture_id')

            logger.info(f"Contest ID: {contest_id}, Lecture ID: {lecture_id}")  # Loguj konkretne dane

            if not contest_id or not lecture_id:
                return JsonResponse({'error': 'Invalid data'}, status=400)

            contest = get_object_or_404(Contest, id=contest_id)
            lecture = get_object_or_404(Lecture, id=lecture_id)

            if ContestLecture.objects.filter(contest=contest, lecture=lecture).exists():
                return JsonResponse({'error': 'Lecture already added to this contest'}, status=400)

            ContestLecture.objects.create(contest=contest, lecture=lecture)

            return JsonResponse({
                'message': 'Lecture added successfully',
                'lecture_id': lecture.id,
                'lecture_name': lecture.name,
                'teacher': f"{lecture.teacher.first_name} {lecture.teacher.last_name}",
                'content_path': lecture.content_path
            })
        except Exception as e:
            logger.error(f"Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def remove_lecture_from_contest(request):
    if request.method == 'POST':
        try:
            logger.info(f"Request body: {request.body}")
            data = json.loads(request.body)
            contest_id = data.get('contest_id')
            lecture_id = data.get('lecture_id')

            logger.info(f"Contest ID: {contest_id}, Lecture ID: {lecture_id}")

            if not contest_id or not lecture_id:
                return JsonResponse({'error': 'Invalid data'}, status=400)

            contest = get_object_or_404(Contest, id=contest_id)
            lecture = get_object_or_404(Lecture, id=lecture_id)

            contest_lecture = ContestLecture.objects.filter(contest=contest, lecture=lecture).first()
            if not contest_lecture:
                return JsonResponse({'error': 'Lecture not assigned to this contest'}, status=400)

            contest_lecture.delete()

            return JsonResponse({
                'message': 'Lecture removed successfully',
                'lecture_id': lecture.id,
                'lecture_name': lecture.name,
                'teacher': f"{lecture.teacher.first_name} {lecture.teacher.last_name}",
                'content_path': lecture.content_path
            })
        except Exception as e:
            logger.error(f"Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)



@method_decorator(login_required, name='dispatch')
class edit_contest_tasks_view(ListView):
    template_name = 'edit_contest_tasks.html'
    context_object_name = 'tasks'
    paginate_by = 10  # Liczba zadań na stronie

    def get_queryset(self):
        contest_id = self.kwargs['contest_id']
        contest = get_object_or_404(Contest, id=contest_id)
        saved_tasks_ids = ContestTask.objects.filter(contest=contest).values_list('task_id', flat=True)

        # Wszystkie dostępne zadania (bez zapisanych)
        tasks = Task.objects.filter(
            (Q(author=self.request.user) | Q(is_public=True)) & ~Q(id__in=saved_tasks_ids)
        ).order_by('id')  # Dodano porządek

        return tasks

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contest_id = self.kwargs['contest_id']
        contest = get_object_or_404(Contest, id=contest_id)

        # Zapisane zadania
        saved_tasks = ContestTask.objects.filter(contest=contest).select_related('task')

        context.update({
            'contest': contest,
            'saved_tasks': saved_tasks,
        })
        return context


@csrf_exempt
def add_task_to_contest(request):
    if request.method == 'POST':
        try:
            logger.info(f"Request body: {request.body}")
            data = json.loads(request.body)
            contest_id = data.get('contest_id')
            task_id = data.get('task_id')

            logger.info(f"Contest ID: {contest_id}, Task ID: {task_id}")

            if not contest_id or not task_id:
                return JsonResponse({'error': 'Invalid data'}, status=400)

            contest = get_object_or_404(Contest, id=contest_id)
            task = get_object_or_404(Task, id=task_id)

            if ContestTask.objects.filter(contest=contest, task=task).exists():
                return JsonResponse({'error': 'Task already added to this contest'}, status=400)

            ContestTask.objects.create(contest=contest, task=task)

            return JsonResponse({
                'message': 'Task added successfully',
                'task_id': task.id,
                'task_name': task.name,
                'author': f"{task.author.first_name} {task.author.last_name}",
                'content_path': task.content_path
            })
        except Exception as e:
            logger.error(f"Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def remove_task_from_contest(request):
    if request.method == 'POST':
        try:
            logger.info(f"Request body: {request.body}")
            data = json.loads(request.body)
            contest_id = data.get('contest_id')
            task_id = data.get('task_id')

            logger.info(f"Contest ID: {contest_id}, Task ID: {task_id}")

            if not contest_id or not task_id:
                return JsonResponse({'error': 'Invalid data'}, status=400)

            contest = get_object_or_404(Contest, id=contest_id)
            task = get_object_or_404(Task, id=task_id)

            contest_task = ContestTask.objects.filter(contest=contest, task=task).first()
            if not contest_task:
                return JsonResponse({'error': 'Task not assigned to this contest'}, status=400)

            contest_task.delete()

            return JsonResponse({
                'message': 'Task removed successfully',
                'task_id': task.id,
                'task_name': task.name,
                'author': f"{task.author.first_name} {task.author.last_name}",
                'content_path': task.content_path
            })
        except Exception as e:
            logger.error(f"Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@method_decorator(login_required, name='dispatch')
class ContestListView(ListView):
    template_name = 'contest_list.html'
    context_object_name = 'user_contests'

    def get_queryset(self):
        # Pobieranie kursów, na które użytkownik jest zapisany
        return ContestSigned.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_contests = self.get_queryset().values_list('contest', flat=True)
        # Pobieranie dostępnych kursów, na które użytkownik nie jest zapisany
        context['available_contests'] = Contest.objects.exclude(id__in=user_contests)
        return context
    
@login_required
def select_contest(request, contest_id):
    # Pobierz rekord ContestSigned dla zalogowanego użytkownika i wybranego konkursu
    contest_signup = get_object_or_404(ContestSigned, contest_id=contest_id, user=request.user)

    # Zresetuj is_selected dla wszystkich kursów użytkownika
    ContestSigned.objects.filter(user=request.user).update(is_selected=False)

    # Ustaw is_selected na true dla wybranego kursu
    contest_signup.is_selected = True
    contest_signup.save()

    # Odśwież stronę
    return redirect('contest_list_view')
    
@login_required
def sign_to_contest(request, contest_id):
    contest = get_object_or_404(Contest, id=contest_id)
    
    # Sprawdzenie, czy użytkownik już jest zapisany na ten konkurs
    if ContestSigned.objects.filter(contest=contest, user=request.user).exists():
        return redirect('/')
    
    if request.method == "POST":
        # Pobranie hasła z formularza
        password = request.POST.get('password', '')
        
        # Weryfikacja hasła, jeżeli jest ustawione
        if contest.password and not contest.check_contest_password(password):
            messages.error(request, 'Niepoprawne hasło.')
            return render(request, 'sign_to_contest.html', {'contest': contest})
        
        # Tworzenie lub aktualizacja rekordów w ContestSigned
        ContestSigned.objects.update_or_create(
            contest=contest,
            user=request.user,
            defaults={'is_selected': True}
        )
        
        # Ustawienie is_selected = False w pozostałych rekordach użytkownika
        ContestSigned.objects.filter(user=request.user).exclude(contest=contest).update(is_selected=False)
        
        # Przekierowanie na stronę główną
        return redirect('/')
    
    # GET - wyświetlenie szczegółów konkursu
    return render(request, 'sign_to_contest.html', {'contest': contest})



@login_required
def lecture_list(request):
    user = request.user

    # Pobranie rekordów ContestSigned
    signed_contests = ContestSigned.objects.filter(user=user, is_selected=True)

    # Jeśli nie ma żadnego wybranego konkursu
    if not signed_contests.exists():
        return render(request, "lecture_list.html", {"error_message": "Proszę wybrać kurs w zakładce kursy!"})

    # Jeśli jest więcej niż jeden wybrany konkurs
    if signed_contests.count() > 1:
        return render(request, "lecture_list.html", {"error_message": "Wystąpił błąd! Wybierz kurs ponownie!"})

    # Pobranie wybranego konkursu
    selected_contest = signed_contests.first().contest

    # Pobranie wykładów powiązanych z wybranym konkursem
    contest_lectures = ContestLecture.objects.filter(contest=selected_contest).select_related('lecture', 'lecture__teacher')

    context = {
        "selected_contest": selected_contest,
        "contest_lectures": contest_lectures,
    }

    return render(request, "lecture_list.html", context)


@login_required
def task_list(request):
    user = request.user

    # Pobranie rekordów ContestSigned
    signed_contests = ContestSigned.objects.filter(user=user, is_selected=True)

    # Jeśli nie ma żadnego wybranego konkursu
    if not signed_contests.exists():
        return render(request, "task_list.html", {"error_message": "Proszę wybrać kurs w zakładce kursy!"})

    # Jeśli jest więcej niż jeden wybrany konkurs
    if signed_contests.count() > 1:
        return render(request, "task_list.html", {"error_message": "Wystąpił błąd! Wybierz kurs ponownie!"})

    # Pobranie wybranego konkursu
    selected_contest = signed_contests.first().contest

    # Pobranie zadań powiązanych z wybranym konkursem
    contest_tasks = ContestTask.objects.filter(contest=selected_contest).select_related('task')

    # Przyporządkowanie najlepszych wyników do zadań
    tasks_with_scores = []
    for contest_task in contest_tasks:
        best_solution = Solution.objects.filter(
            contest_task=contest_task,
            author=user
        ).aggregate(max_points=Max('final_points'))

        # Pobieramy wynik lub ustawiamy 0, jeśli nie znaleziono rozwiązania
        score = best_solution['max_points'] or 0
        tasks_with_scores.append({
            "task": contest_task.task,
            "score": score,
        })

    context = {
        "selected_contest": selected_contest,
        "tasks_with_scores": tasks_with_scores,
    }

    return render(request, "task_list.html", context)


@method_decorator(login_required, name='dispatch')
class UserSolutionsView(ListView):
    model = Solution
    template_name = 'user_solutions.html'
    context_object_name = 'solutions'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        selected_contests = ContestSigned.objects.filter(user=user, is_selected=True)

        if selected_contests.count() == 1:
            contest = selected_contests.first().contest
            return Solution.objects.filter(
                author=user,
                contest_task__contest=contest
            ).order_by('-send_date')
        else:
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        selected_contests = ContestSigned.objects.filter(user=user, is_selected=True)

        if selected_contests.count() == 0:
            context['error_message'] = "Nie wybrano kursu!"
        elif selected_contests.count() > 1:
            context['error_message'] = "Wystąpił błąd! Proszę wybrać kurs ponownie!"
        else:
            context['error_message'] = None

        # Przetwarzanie rozwiązań
        for solution in context['solutions']:
            if solution.final_points is not None:
                solution.color = f"rgb({255 - int(solution.final_points * 2.55)}, {int(solution.final_points * 2.55)}, 0)"
            else:
                solution.color = None

        return context

@login_required
def send_solution_view(request):
    user = request.user
    context = {
        'contest_found': False,
        'form': None,
        'tasks': []
    }

    # GET request handling
    if request.method == 'GET':
        signed_contests = ContestSigned.objects.filter(user=user, is_selected=True)

        if signed_contests.count() == 1:
            signed_contest = signed_contests.first()
            contest_tasks = ContestTask.objects.filter(contest=signed_contest.contest)

            context['contest_found'] = True
            context['form'] = SendSolutionForm(tasks=contest_tasks)
            context['tasks'] = contest_tasks
        else:
            context['error_message'] = "Wystąpił błąd, wybierz nowy kurs!"

        return render(request, 'send_solution.html', context)

    # POST request handling
    elif request.method == 'POST':
        contest_tasks = ContestTask.objects.filter(contest__contestsigned__user=user, contest__contestsigned__is_selected=True)
        form = SendSolutionForm(request.POST, request.FILES, tasks=contest_tasks)

        if not form.is_valid():
            context['form'] = form
            context['error_message'] = "Formularz zawiera błędy. Proszę poprawić i spróbować ponownie."
            return render(request, 'send_solution.html', context)

        # Validate file extension based on language
        solution_file = request.FILES.get('solution_file')
        if solution_file:
            lang = form.cleaned_data['lang']
            file_extension = solution_file.name.split('.')[-1].lower()
            valid_extensions = {
                'C/C++': ['c', 'cpp', 'cc'],
                'Java': ['java'],
                'C#': ['cs']
            }

            if file_extension not in valid_extensions.get(lang, []):
                context['form'] = form
                context['error_message'] = "Nieprawidłowe rozszerzenie pliku dla wybranego języka."
                return render(request, 'send_solution.html', context)

        # Prepare solution folder and file path
        try:
            contest_task = form.cleaned_data['contest_task']

            time_now = datetime.now()
        
            if contest_task.contest.start_date and time_now.date() < contest_task.contest.start_date:
                context['form'] = form
                context['error_message'] = "Kurs się jeszcze nie rozpoczął!"
                return render(request, 'send_solution.html', context)
            
            if contest_task.contest.end_date and time_now.date() > contest_task.contest.end_date:
                context['form'] = form
                context['error_message'] = "Kurs się już zakończył!"
                return render(request, 'send_solution.html', context)

            contest_name = contest_task.contest.name
            task_name = contest_task.task.name
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
            random_suffix = random.randint(1000, 9999)
            folder_name = f"{timestamp}_{contest_name}_{task_name}_{user.username}_{random_suffix}"
            folder_path = os.path.join('media', 'solutions', folder_name)

            os.makedirs(folder_path, exist_ok=True)

            file_path = os.path.join(folder_path, solution_file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in solution_file.chunks():
                    destination.write(chunk)

            src_path = os.path.join(folder_name, solution_file.name)
        except Exception as e:
            context['form'] = form
            context['error_message'] = f"Błąd podczas zapisywania pliku: {str(e)}"
            return render(request, 'send_solution.html', context)

        # Save solution record
        solution = form.save(commit=False)
        solution.author = user
        solution.send_date = now()
        solution.src_path = src_path
        solution.status = 'waiting'
        solution.save()

        # Execute the appropriate task based on language
        if lang == 'C/C++':
            execute_cpp.delay(solution.id)
        elif lang == 'Java':
            execute_java.delay(solution.id)
        elif lang == 'C#':
            execute_cs.delay(solution.id)

        return redirect('user_solutions')


@login_required
def solution_raport_view(request, id):
    solution = get_object_or_404(Solution, pk=id)

    # Check user permissions
    user = request.user
    if not (
        user == solution.author or 
        user == solution.contest_task.contest.teacher or 
        user.role == 'admin'
    ):
        return redirect('home')

    # Prepare data for rendering
    if solution.status != 'done':
        context = {
            'solution': solution,
            'is_done': False,
        }
        return render(request, 'solution_raport.html', context)

    # Fetch test results grouped by TestGroup
    grouped_results = {}
    ungrouped_results = []

    results = SolutionTestResult.objects.filter(solution=solution).select_related(
        'test', 'test__group'
    )

    for result in results:
        group_name = result.test.group.name if result.test.group else 'N/A'
        if group_name not in grouped_results:
            grouped_results[group_name] = []
        grouped_results[group_name].append(result)

    context = {
        'solution': solution,
        'is_done': True,
        'grouped_results': grouped_results,
        'ungrouped_results': ungrouped_results,
    }
    return render(request, 'solution_raport.html', context)


@login_required
def contest_ranking_view(request):
    user = request.user

    # Pobranie wybranego konkursu
    contest_signups = ContestSigned.objects.filter(user=user, is_selected=True)
    if contest_signups.count() != 1:
        return render(request, 'contest_ranking.html', {
            'error': 'Nieprawidłowa liczba wybranych konkursów. Skontaktuj się z administratorem.'
        })

    contest = contest_signups.first().contest
    contest_tasks = ContestTask.objects.filter(contest=contest)
    tasks_data = {contest_task.task.id: contest_task.task.special_id for contest_task in contest_tasks}

    # Ranking zamrożony - warunki
    frozen_ranking = contest.frozen_ranking
    extra_filter = Q()
    if frozen_ranking and not (user.role == 'admin' or contest.teacher == user):
        extra_filter = Q(send_date__lt=frozen_ranking)

    # Pobieranie danych do rankingu
    rankings = []
    for signup in ContestSigned.objects.filter(contest=contest):
        person = signup.user
        solutions = []
        total_points = 0

        for task_id in tasks_data.keys():
            best_solution = Solution.objects.filter(
                contest_task__contest=contest,
                contest_task__task_id=task_id,
                author=person,
                status='done'
            ).filter(extra_filter).annotate(
                points=F('final_points')
            ).order_by('-points', '-send_date').first()

            points = best_solution.final_points if best_solution and best_solution.final_points else 0
            solutions.append(points)
            total_points += points

        if total_points > 0:  # Pomijamy osoby bez punktów
            rankings.append({
                'user': person,
                'solutions': solutions,
                'total_points': total_points
            })

    # Sortowanie rankingu
    rankings = sorted(rankings, key=lambda x: -x['total_points'])
    rank = 1
    last_points = None
    for i, entry in enumerate(rankings):
        if last_points != entry['total_points']:
            rank = i + 1
            last_points = entry['total_points']
        entry['rank'] = rank

    return render(request, 'contest_ranking.html', {
        'contest': contest,
        'tasks': tasks_data,
        'rankings': rankings,
    })


@login_required
def question_user_view(request):
    # Sprawdzenie aktualnie wybranego kursu
    selected_contests = ContestSigned.objects.filter(user=request.user, is_selected=True)
    if selected_contests.count() != 1:
        return render(request, 'question_user.html', {
            'error': "Proszę wybrać jeden aktualny kurs."
        })
    
    selected_contest = selected_contests.first().contest

    # Formularz
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.user = request.user
            question.contest = selected_contest
            question.date_posted = now()
            question.save()
            return redirect('question_user_view')
    else:
        form = QuestionForm()
        # Ogranicz zadania w formularzu do aktualnego kursu
        form.fields['task'].queryset = Task.objects.filter(
            contesttask__contest=selected_contest
        )

    # Pobranie pytań usera dla aktualnego kursu
    questions = Question.objects.filter(user=request.user, contest=selected_contest).order_by('-date_posted')
    paginator = Paginator(questions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'question_user.html', {
        'form': form,
        'page_obj': page_obj,
        'contest': selected_contest,
    })

@login_required
def question_content_view(request, question_id):
    # Pobranie pytania na podstawie ID
    try:
        question = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        raise Http404("Pytanie nie istnieje.")

    # Sprawdzenie uprawnień
    if not (
        question.user == request.user or
        question.contest.teacher == request.user or
        request.user.role == 'admin'
    ):
        return redirect('home')

    # Renderowanie szczegółów pytania
    return render(request, 'question_content.html', {
        'question': question,
    })


@login_required
def question_teacher_view(request):
    # Pobranie odpowiednich kursów w zależności od roli użytkownika
    if request.user.role == 'admin':
        contests = Contest.objects.annotate(
            unanswered_count=Count('question', filter=Q(question__answer__isnull=True))
        )
    else:
        contests = Contest.objects.filter(teacher=request.user).annotate(
            unanswered_count=Count('question', filter=Q(question__answer__isnull=True))
        )

    return render(request, 'question_teacher.html', {
        'contests': contests,
    })

@login_required
def question_contest_view(request, contest_id):
    # Pobranie kursu na podstawie ID
    try:
        contest = Contest.objects.get(id=contest_id)
    except Contest.DoesNotExist:
        raise Http404("Kurs nie istnieje.")

    # Sprawdzenie uprawnień
    if not (request.user == contest.teacher or request.user.role == 'admin'):
        return redirect('home')

    # Pobranie wszystkich pytań do kursu, posortowanych od najnowszego
    questions = Question.objects.filter(contest=contest).order_by('-date_posted')

    return render(request, 'question_contest.html', {
        'contest': contest,
        'questions': questions,
    })

@login_required
def question_answer_view(request, question_id):
    # Pobranie pytania na podstawie ID
    try:
        question = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        raise Http404("Pytanie nie istnieje.")

    # Sprawdzenie uprawnień
    if not (
        request.user.role == 'admin' or 
        request.user == question.contest.teacher
    ):
        return redirect('home')

    # Sprawdzenie, czy pytanie zostało już odpowiedziane
    if question.answer:
        return redirect('question_content_view', question_id=question.id)

    if request.method == 'POST':
        form = AnswerForm(request.POST)
        if form.is_valid():
            # Sprawdzenie ponownie, czy pytanie zostało odpowiedziane
            question.refresh_from_db()
            if question.answer:
                return redirect('question_content_view', question_id=question.id)

            # Zapis odpowiedzi
            question.answer = form.cleaned_data['answer']
            question.user_answered = request.user
            question.save()

            return redirect('question_content_view', question_id=question.id)
    else:
        form = AnswerForm()

    return render(request, 'question_answer.html', {
        'question': question,
        'form': form,
    })

@user_not_teacher
def download_file(request, test_id, in_out):
    try:
        test = Test.objects.get(id=test_id)
    except Test.DoesNotExist:
        raise Http404("File not found")
    
    file_path = os.path.join(test.task.content_path, 'tests', test.name)

    if in_out == 1:
        file_path = os.path.join(file_path, test.in_file)
        filename = test.in_file
    elif in_out == 2:
        file_path = os.path.join(file_path, test.out_file)
        filename = test.out_file
    else:
        raise Http404("File not found")
    
    # Otwieramy plik w trybie binarnym
    response = FileResponse(open(file_path, 'rb'))
    
    # Ustawiamy nagłówki Content-Disposition, aby wymusić pobieranie
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def delete_group(request, group_id):
    if request.method == "POST":
        try:
            with transaction.atomic():
                group = get_object_or_404(TestGroup, id=group_id)
                
                # Zmiana grupy na NULL dla powiązanych testów
                Test.objects.filter(group=group).update(group=None)
                
                # Usunięcie grupy
                group.delete()
            
            return JsonResponse({"status": "success", "message": "Grupa została pomyślnie usunięta."})
        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Wystąpił błąd: {str(e)}"})


def delete_test(request, test_id):
    if request.method == "POST":
        try:
            # Pobierz test
            test = get_object_or_404(Test, id=test_id)
            
            # Usuń test
            test.delete()
            
            return JsonResponse({"status": "success", "message": "Test został pomyślnie usunięty."})
        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Wystąpił błąd: {str(e)}"})
        

