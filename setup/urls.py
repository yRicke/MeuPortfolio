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
from app import api, mcp

handler400 = 'app.error_views.erro_400'
handler403 = 'app.error_views.erro_403'
handler404 = 'app.error_views.erro_404'
handler500 = 'app.error_views.erro_500'

urlpatterns = [
    path('admindjango/', admin.site.urls),
    path('', views.index, name='index'),
    path('sobre/', views.sobre, name='sobre'),

    path('entrar/', views.entrar, name='entrar'),
    path('sair/', views.sair, name='sair'),

    path('painel/projetos/', views.painel_projetos, name='painel_projetos'),
    path('painel/api/', views.painel_chave_api, name='painel_chave_api'),
    path('adicionar_projeto/', views.adicionar_projeto, name='adicionar_projeto'),
    path('projeto/<int:projeto_id>/', views.detalhe_projeto, name='detalhe_projeto'),
    path('editar_projeto/<int:projeto_id>/', views.editar_projeto, name='editar_projeto'),
    path('deletar_projeto/<int:projeto_id>/', views.deletar_projeto, name='deletar_projeto'),

    path('api/v1/', api.raiz_api, name='raiz_api'),
    path('api/v1/projetos/', api.colecao_projetos, name='colecao_projetos_api'),
    path(
        'api/v1/projetos/organizacao/',
        api.organizacao_projetos_api,
        name='organizacao_projetos_api',
    ),
    path(
        'api/v1/projetos/<int:projeto_id>/',
        api.detalhe_projeto_api,
        name='detalhe_projeto_api',
    ),
    path(
        'api/v1/projetos/<int:projeto_id>/imagens/',
        api.colecao_imagens_api,
        name='colecao_imagens_api',
    ),
    path(
        'api/v1/projetos/<int:projeto_id>/imagens/ordem/',
        api.organizacao_imagens_api,
        name='organizacao_imagens_api',
    ),
    path(
        'api/v1/projetos/<int:projeto_id>/imagens/<int:imagem_id>/',
        api.detalhe_imagem_api,
        name='detalhe_imagem_api',
    ),
    path('mcp/', mcp.endpoint_mcp, name='endpoint_mcp'),
]

if settings.DATABASE_URL:
    urlpatterns += [
        path('media/<path:caminho>', views.servir_midia, name='servir_midia'),
    ]
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

