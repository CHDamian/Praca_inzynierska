from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import user_passes_test

def not_logged_in_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def logged_in_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def user_logged_in(view_func):
    return user_passes_test(lambda u: not u.is_authenticated, login_url='login')(view_func)

def user_not_teacher(view_func):
    def check_role(user):
        return user.role in ['teacher', 'admin']
    return user_passes_test(check_role, login_url='home')(view_func)

def user_not_admin(view_func):
    return user_passes_test(lambda u: u.role == 'admin', login_url='home')(view_func)
