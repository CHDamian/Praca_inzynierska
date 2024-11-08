from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('contest_manager/', views.contest_manager_view.as_view(), name='contest_manager_view'),
    path('lecture_manager/', views.lecture_manager_view.as_view(), name='lecture_manager_view'),
    path('task_manager/', views.task_manager_view.as_view(), name='task_manager_view'),
]