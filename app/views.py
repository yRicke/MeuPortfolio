import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from app.models import ArquivoMidia, ChaveAPI, Projeto
from app.project_service import ErroAPI, organizar_projetos

# Create your views here.


def _interpretar_mes(valor):
    if not valor:
        return None
    return datetime.strptime(valor, '%Y-%m').date().replace(day=1)


def index(request):
    projetos = Projeto.objects.all()
    return render(request, 'index.html', {
        'projetos': projetos,
        'projeto_destaque': (
            projetos.filter(destaque=True).first() or projetos.first()
        ),
    })


def servir_midia(request, caminho):
    arquivo = get_object_or_404(ArquivoMidia, nome=caminho)
    resposta = HttpResponse(
        bytes(arquivo.conteudo),
        content_type=arquivo.tipo_conteudo,
    )
    resposta['Cache-Control'] = 'public, max-age=31536000, immutable'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


@login_required(login_url='entrar')
@require_http_methods(['GET', 'POST'])
def painel_projetos(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'GET':
        return render(request, 'painel_projetos.html', {
            'projetos': Projeto.objects.all(),
        })

    try:
        dados = json.loads(request.body or '{}')
        ordem = [int(projeto_id) for projeto_id in dados.get('ordem', [])]
        destaque = (
            int(dados['destaque'])
            if dados.get('destaque') is not None
            else None
        )
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return JsonResponse({
            'ok': False,
            'mensagem': 'Os dados enviados são inválidos.',
        }, status=400)

    try:
        resultado = organizar_projetos(ordem, destaque)
    except ErroAPI as erro:
        return JsonResponse({
            'ok': False,
            'mensagem': erro.mensagem,
        }, status=erro.status)

    return JsonResponse({
        'ok': True,
        'mensagem': 'Organização salva com sucesso.',
        **resultado,
    })


@login_required(login_url='entrar')
@never_cache
@require_http_methods(['GET', 'POST'])
def painel_chave_api(request):
    if not request.user.is_staff:
        raise PermissionDenied

    nova_chave = None
    credencial = ChaveAPI.objects.filter(identificador=1).first()
    if request.method == 'POST':
        credencial, nova_chave = ChaveAPI.rotacionar(request.user)

    resposta = render(request, 'painel_chave_api.html', {
        'credencial': credencial,
        'nova_chave': nova_chave,
    })
    resposta['Cache-Control'] = 'no-store'
    return resposta


def detalhe_projeto(request, projeto_id):
    projeto = get_object_or_404(
        Projeto.objects.prefetch_related('imagens'),
        id=projeto_id,
    )
    return render(request, 'detalhe_projeto.html', {
        'projeto': projeto,
        'imagens_projeto': list(projeto.imagens.all()),
    })


@login_required(login_url='entrar')
def adicionar_projeto(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descricao = request.POST.get('descricao')
        capa = request.FILES.get('capa')
        url = request.POST.get('url', None)
        data_desenvolvimento = request.POST.get('data_desenvolvimento')
        imagens = request.FILES.getlist('imagens')
        try:
            with transaction.atomic():
                projeto = Projeto.criar_projeto(
                    titulo,
                    descricao,
                    capa,
                    url,
                    _interpretar_mes(data_desenvolvimento),
                )
                projeto.adicionar_imagens(imagens)
            messages.success(request, 'Projeto adicionado com sucesso.')
        except (TypeError, ValueError):
            messages.error(request, 'Informe uma data de desenvolvimento válida.')
        except Exception:
            messages.error(
                request,
                'Erro ao adicionar projeto. Verifique os dados e tente novamente.',
            )
        return redirect('index')
    return render(request, 'adicionar_projeto.html')


@login_required(login_url='entrar')
def editar_projeto(request, projeto_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    projeto = get_object_or_404(
        Projeto.objects.prefetch_related('imagens'),
        id=projeto_id,
    )
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descricao = request.POST.get('descricao')
        capa = request.FILES.get('capa')
        url = request.POST.get('url', None)
        data_desenvolvimento = request.POST.get('data_desenvolvimento')
        novas_imagens = request.FILES.getlist('imagens')
        imagens_para_remover = request.POST.getlist('remover_imagens')
        if capa is None:
            capa = projeto.capa
        try:
            with transaction.atomic():
                projeto.atualizar_projeto(
                    titulo,
                    descricao,
                    capa,
                    url,
                    _interpretar_mes(data_desenvolvimento),
                )
                projeto.imagens.filter(pk__in=imagens_para_remover).delete()
                projeto.adicionar_imagens(novas_imagens)
            messages.success(request, 'Projeto atualizado com sucesso.')
            return redirect('editar_projeto', projeto_id=projeto.id)
        except (TypeError, ValueError):
            messages.error(request, 'Informe uma data de desenvolvimento válida.')
        except Exception:
            messages.error(request, 'Erro ao atualizar projeto.')
    return render(request, 'editar_projeto.html', {'projeto': projeto})

@login_required(login_url='entrar')
@require_POST
def deletar_projeto(request, projeto_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    projeto = get_object_or_404(Projeto, id=projeto_id)
    try:
        projeto.deletar_projeto()
        messages.success(request, 'Projeto removido.')
    except Exception:
        messages.error(request, 'Erro ao remover projeto.')
    return redirect('index')

def entrar(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Logado com sucesso.')
            proxima_url = request.POST.get('next') or request.GET.get('next')
            if proxima_url and url_has_allowed_host_and_scheme(
                proxima_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(proxima_url)
            return redirect('index')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    return render(request, 'entrar.html', {
        'next': request.POST.get('next') or request.GET.get('next', ''),
    })

def sair(request):
    logout(request)
    return redirect('index')

def sobre(request):
    return redirect(f'{reverse("index")}#sobre')
