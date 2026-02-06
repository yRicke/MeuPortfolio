from django.shortcuts import render, redirect
from app.models import Projeto
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Create your views here.

def index(request):
    projetos = Projeto.objects.all()
    return render(request, 'index.html', {'projetos': projetos})

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
    return render(request, 'sobre.html')