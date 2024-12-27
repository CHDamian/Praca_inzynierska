from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("", views.home_view, name="home"),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('contest_manager/', views.contest_manager_view.as_view(), name='contest_manager_view'),
    path('lecture_manager/', views.lecture_manager_view.as_view(), name='lecture_manager_view'),
    path('task_manager/', views.task_manager_view.as_view(), name='task_manager_view'),
    path('add_lecture/', views.add_lecture_view.as_view(), name='add_lecture'),
    path('pdf_page/<str:pdf_path>/', views.pdf_page, name='pdf_page'),
    path('add_task/', views.add_task_view.as_view(), name='add_task'),
    path('edit_task/<int:task_id>/', views.edit_task_view, name='edit_task'),
    path('create-test/', views.create_test_view, name='create_test'),
    path('edit-test/', views.edit_test_view, name='edit_test'),
    path('update-group/<int:group_id>/', views.update_group_view, name='update_group'),
    path('create-group/<int:task_id>/', views.create_group_view, name='create_group'),
    path('add_contest/', views.add_contest_view.as_view(), name='add_contest'),
    path('edit_contest/<int:contest_id>/', views.edit_contest_view, name='edit_contest'),
    path('edit_contest_lectures/<int:contest_id>/', views.edit_contest_lectures_view.as_view(), name='edit_contest_lectures'),
    path('add-lecture-to-contest/', views.add_lecture_to_contest, name='add_lecture_to_contest'),
    path('remove-lecture-from-contest/', views.remove_lecture_from_contest, name='remove_lecture_from_contest'),
    path('edit_contest_tasks/<int:contest_id>/', views.edit_contest_tasks_view.as_view(), name='edit_contest_tasks'),
    path('add-task-to-contest/', views.add_task_to_contest, name='add_task_to_contest'),
    path('remove-task-from-contest/', views.remove_task_from_contest, name='remove_task_from_contest'),
    path('contests/', views.ContestListView.as_view(), name='contest_list_view'),
    path('contest/sign/<int:contest_id>/', views.sign_to_contest, name='sign_to_contest'),
    path('lecture_list/', views.lecture_list, name='lecture_list'),
    path('task_list/', views.task_list, name='task_list'),
    path('user-solutions/', views.UserSolutionsView.as_view(), name='user_solutions'),
    path('send_solution/', views.send_solution_view, name='send_solution'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)