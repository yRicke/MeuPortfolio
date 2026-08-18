from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app.models import ChaveAPI


def exigir_chave_api(view):
    @csrf_exempt
    @wraps(view)
    def view_autenticada(request, *args, **kwargs):
        autorizacao = request.headers.get('Authorization', '')
        esquema, separador, chave = autorizacao.partition(' ')

        if (
            not separador
            or esquema.lower() != 'bearer'
            or not ChaveAPI.autenticar(chave.strip())
        ):
            resposta = JsonResponse({
                'erro': {
                    'codigo': 'nao_autorizado',
                    'mensagem': 'Informe uma chave de API valida como Bearer token.',
                },
            }, status=401)
            resposta['WWW-Authenticate'] = 'Bearer'
            resposta['Cache-Control'] = 'no-store'
            return resposta

        resposta = view(request, *args, **kwargs)
        resposta['Cache-Control'] = 'no-store'
        return resposta

    return view_autenticada
