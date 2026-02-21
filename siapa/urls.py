"""
URL configuration for siapa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
# from pemilu2024 import views # Dihapus karena app sudah hilang
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect

def dummy_landing(request):
    return render(request, 'landing.html')

def dummy_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard_overview')
        
    error = None
    if request.method == "POST":
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('dashboard_overview')
        else:
            error = "Username atau password salah bos!"
            
    return render(request, 'login.html', {'error': error})

def dummy_logout(request):
    logout(request)
    return redirect('landing')

def dummy_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('custom_login')
    return render(request, 'dashboard.html')

def dummy_map(request):
    if not request.user.is_authenticated:
        return redirect('custom_login')
    return render(request, 'dashboard_map.html')

urlpatterns = [
    path('', dummy_landing, name='landing'),
    path('xxx/', admin.site.urls),
    path('login/', dummy_login, name='custom_login'),
    path('logout/', dummy_logout, name='custom_logout'),
    path('dashboard/', dummy_dashboard, name='dashboard_overview'),
    path('map/', dummy_map, name='dashboard_map'),
]

from django.urls import re_path
from django.views.static import serve

# Serve media and static files explicitly
urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
