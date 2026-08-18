from django.http import JsonResponse
from django.shortcuts import render


ERROS = {
    400: {
        'titulo': 'Requisição inválida',
        'mensagem': (
            'Não foi possível entender os dados enviados. Revise a solicitação '
            'e tente novamente.'
        ),
    },
    403: {
        'titulo': 'Acesso negado',
        'mensagem': (
            'Sua conta não possui permissão para acessar esta área ou concluir '
            'esta ação.'
        ),
    },
    404: {
        'titulo': 'Página não encontrada',
        'mensagem': (
            'O endereço pode ter mudado ou o conteúdo que você procura não existe.'
        ),
    },
    405: {
        'titulo': 'Ação não permitida',
        'mensagem': 'Esta ação não está disponível para o endereço acessado.',
    },
    500: {
        'titulo': 'Erro interno',
        'mensagem': (
            'Ocorreu uma falha inesperada. Tente novamente em instantes; se o '
            'problema continuar, retorne à página inicial.'
        ),
    },
}


def _resposta_erro(request, status, detalhe=None):
    dados = {
        'codigo': str(status),
        **ERROS[status],
    }
    if detalhe:
        dados['detalhe'] = detalhe

    if request.path.startswith('/api/'):
        resposta = JsonResponse({
            'erro': {
                'codigo': f'erro_{status}',
                'mensagem': dados['mensagem'],
            },
        }, status=status)
    elif request.path.startswith('/mcp/'):
        resposta = JsonResponse({
            'jsonrpc': '2.0',
            'id': None,
            'error': {
                'code': -32603 if status == 500 else -32600,
                'message': dados['mensagem'],
            },
        }, status=status)
    else:
        resposta = render(request, 'erro.html', dados, status=status)

    resposta['Cache-Control'] = 'no-store'
    return resposta


def erro_400(request, exception=None):
    return _resposta_erro(request, 400)


def erro_403(request, exception=None):
    return _resposta_erro(request, 403)


def erro_csrf(request, reason=''):
    return _resposta_erro(
        request,
        403,
        'A sessão do formulário expirou. Atualize a página antes de tentar novamente.',
    )


def erro_404(request, exception=None):
    return _resposta_erro(request, 404)


def erro_405(request, metodos_permitidos=None):
    detalhe = None
    if metodos_permitidos:
        detalhe = f'Métodos permitidos: {metodos_permitidos}.'
    resposta = _resposta_erro(request, 405, detalhe)
    if metodos_permitidos:
        resposta['Allow'] = metodos_permitidos
    return resposta


def erro_500(request):
    return _resposta_erro(request, 500)
