from app.error_views import erro_405


class PaginaErroMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if resposta.status_code == 405:
            return erro_405(request, resposta.headers.get('Allow'))
        return resposta
