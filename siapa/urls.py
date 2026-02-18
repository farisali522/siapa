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
from pemilu2024 import views
from django.shortcuts import render

urlpatterns = [
    path('', views.landing, name='landing'),
    path('admin/', admin.site.urls),
    path('map/', views.dashboard_peta, name='dashboard_peta'),
    path('get_geo_data/', views.get_geo_data, name='get_geo_data'),
    path('get_kecamatan/', views.get_kecamatan, name='get_kecamatan'),
    path('get_desa/', views.get_desa, name='get_desa'),
]

from django.urls import re_path
from django.views.static import serve

# Serve media and static files explicitly
urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
