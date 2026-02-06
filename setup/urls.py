"""
URL configuration for setup project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admindjango/', admin.site.urls),
    path('', views.index, name='index'),
    path('sobre/', views.sobre, name='sobre'),

    path('entrar/', views.entrar, name='entrar'),
    path('sair/', views.sair, name='sair'),

    path('adicionar_projeto/', views.adicionar_projeto, name='adicionar_projeto'),
    path('editar_projeto/<int:projeto_id>/', views.editar_projeto, name='editar_projeto'),
    path('deletar_projeto/<int:projeto_id>/', views.deletar_projeto, name='deletar_projeto'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

