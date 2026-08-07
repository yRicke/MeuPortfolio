import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.models import Projeto

# Create your views here.

def index(request):
    projetos = Projeto.objects.all()
    return render(request, 'index.html', {
        'projetos': projetos,
        'projeto_destaque': (
            projetos.filter(destaque=True).first() or projetos.first()
        ),
    })


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

    if len(ordem) != len(set(ordem)):
        return JsonResponse({
            'ok': False,
            'mensagem': 'A ordem contém projetos repetidos.',
        }, status=400)

    with transaction.atomic():
        projetos = list(Projeto.objects.select_for_update())
        projetos_por_id = {projeto.pk: projeto for projeto in projetos}

        if set(ordem) != set(projetos_por_id):
            return JsonResponse({
                'ok': False,
                'mensagem': 'A lista de projetos está incompleta ou desatualizada.',
            }, status=400)

        if ordem and destaque not in projetos_por_id:
            return JsonResponse({
                'ok': False,
                'mensagem': 'Escolha um projeto em destaque.',
            }, status=400)

        Projeto.objects.filter(destaque=True).update(destaque=False)

        for posicao, projeto_id in enumerate(ordem):
            projeto = projetos_por_id[projeto_id]
            projeto.ordem = posicao

        if projetos:
            Projeto.objects.bulk_update(projetos, ('ordem',))
            Projeto.objects.filter(pk=destaque).update(destaque=True)

    return JsonResponse({
        'ok': True,
        'mensagem': 'Organização salva com sucesso.',
        'ordem': ordem,
        'destaque': destaque,
    })


def detalhe_projeto(request, projeto_id):
    projeto = get_object_or_404(Projeto, id=projeto_id)
    return render(request, 'detalhe_projeto.html', {'projeto': projeto})

@login_required(login_url='index')
def adicionar_projeto(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descricao = request.POST.get('descricao')
        capa = request.FILES.get('capa')
        url = request.POST.get('url', None)
        try:
            Projeto.criar_projeto(titulo, descricao, capa, url)
            messages.success(request, 'Projeto adicionado com sucesso.')
        except Exception:
            messages.error(request, 'Erro ao adicionar projeto. Verifique os dados e tente novamente.')
        return redirect('index')
    return render(request, 'adicionar_projeto.html')

@login_required(login_url='index')
def editar_projeto(request, projeto_id):
    projeto = Projeto.objects.get(id=projeto_id)
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descricao = request.POST.get('descricao')
        capa = request.FILES.get('capa')
        url = request.POST.get('url', None)
        if capa is None:
            capa = projeto.capa
        try:
            projeto.atualizar_projeto(titulo, descricao, capa, url)
            messages.success(request, 'Projeto atualizado com sucesso.')
        except Exception:
            messages.error(request, 'Erro ao atualizar projeto.')
    return render(request, 'editar_projeto.html', {'projeto': projeto})

@login_required(login_url='index')
def deletar_projeto(request, projeto_id):
    projeto = Projeto.objects.get(id=projeto_id)
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
            return redirect('index')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    return render(request, 'entrar.html')

def sair(request):
    logout(request)
    return redirect('index')

def sobre(request):
    return redirect(f'{reverse("index")}#sobre')
