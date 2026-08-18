import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from app.api_auth import exigir_chave_api
from app.models import ImagemProjeto, Projeto
from app.project_service import (
    ErroAPI,
    atualizar_projeto,
    criar_projeto,
    decodificar_arquivo,
    decodificar_imagens,
    organizar_imagens,
    organizar_projetos,
    serializar_imagem,
    serializar_projeto,
)


def resposta_erro(erro):
    conteudo = {
        'erro': {
            'codigo': erro.codigo,
            'mensagem': erro.mensagem,
        },
    }
    if erro.campos:
        conteudo['erro']['campos'] = erro.campos
    return JsonResponse(conteudo, status=erro.status)


def _ler_dados(request):
    if request.content_type == 'application/json':
        try:
            dados = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            raise ErroAPI('O corpo da requisicao nao contem JSON valido.') from None
        if not isinstance(dados, dict):
            raise ErroAPI('O corpo JSON deve ser um objeto.')
        return dados
    return request.POST.dict()


def _ler_arquivos(request, dados):
    if request.content_type == 'application/json':
        capa = decodificar_arquivo(dados.get('capa'), 'capa')
        imagens = decodificar_imagens(dados.get('imagens'))
        return capa, imagens
    return request.FILES.get('capa'), request.FILES.getlist('imagens')


def _buscar_projeto(projeto_id):
    projeto = Projeto.objects.prefetch_related('imagens').filter(pk=projeto_id).first()
    if not projeto:
        raise ErroAPI('Projeto nao encontrado.', 'nao_encontrado', 404)
    return projeto


@exigir_chave_api
@require_http_methods(['GET'])
def raiz_api(request):
    return JsonResponse({
        'nome': 'API de projetos do portfolio',
        'versao': 'v1',
        'mcp': request.build_absolute_uri('/mcp/'),
        'recursos': {
            'projetos': request.build_absolute_uri('/api/v1/projetos/'),
            'organizacao': request.build_absolute_uri(
                '/api/v1/projetos/organizacao/'
            ),
        },
    })


@exigir_chave_api
@require_http_methods(['GET', 'POST'])
def colecao_projetos(request):
    if request.method == 'GET':
        projetos = Projeto.objects.prefetch_related('imagens')
        return JsonResponse({
            'resultados': [
                serializar_projeto(projeto, request)
                for projeto in projetos
            ],
            'total': projetos.count(),
        })

    try:
        dados = _ler_dados(request)
        capa, imagens = _ler_arquivos(request, dados)
        projeto = criar_projeto(dados, capa, imagens)
    except ErroAPI as erro:
        return resposta_erro(erro)
    return JsonResponse(
        {'projeto': serializar_projeto(projeto, request)},
        status=201,
    )


@exigir_chave_api
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def detalhe_projeto_api(request, projeto_id):
    try:
        projeto = _buscar_projeto(projeto_id)
        if request.method == 'GET':
            return JsonResponse({'projeto': serializar_projeto(projeto, request)})
        if request.method == 'DELETE':
            projeto.deletar_projeto()
            return HttpResponse(status=204)

        dados = _ler_dados(request)
        capa, imagens = _ler_arquivos(request, dados)
        projeto = atualizar_projeto(
            projeto,
            dados,
            capa,
            imagens,
            substituir=request.method == 'PUT',
        )
    except ErroAPI as erro:
        return resposta_erro(erro)
    return JsonResponse({'projeto': serializar_projeto(projeto, request)})


@exigir_chave_api
@require_http_methods(['PATCH'])
def organizacao_projetos_api(request):
    try:
        dados = _ler_dados(request)
        if 'ordem' not in dados:
            raise ErroAPI(
                'O campo ordem e obrigatorio.',
                campos={'ordem': ['Este campo e obrigatorio.']},
            )
        resultado = organizar_projetos(dados['ordem'], dados.get('destaque'))
    except ErroAPI as erro:
        return resposta_erro(erro)
    return JsonResponse(resultado)


@exigir_chave_api
@require_http_methods(['POST'])
def colecao_imagens_api(request, projeto_id):
    try:
        projeto = _buscar_projeto(projeto_id)
        dados = _ler_dados(request)
        _, imagens = _ler_arquivos(request, dados)
        if not imagens:
            raise ErroAPI(
                'Envie ao menos uma imagem.',
                campos={'imagens': ['Este campo e obrigatorio.']},
            )
        adicionadas = projeto.adicionar_imagens(imagens)
    except ErroAPI as erro:
        return resposta_erro(erro)
    except (OSError, ValidationError, ValueError):
        return resposta_erro(ErroAPI(
            'Uma das imagens enviadas e invalida.',
            'imagem_invalida',
        ))
    return JsonResponse({
        'imagens': [serializar_imagem(imagem, request) for imagem in adicionadas],
    }, status=201)


@exigir_chave_api
@require_http_methods(['PATCH'])
def organizacao_imagens_api(request, projeto_id):
    try:
        projeto = _buscar_projeto(projeto_id)
        dados = _ler_dados(request)
        if 'ordem' not in dados:
            raise ErroAPI(
                'O campo ordem e obrigatorio.',
                campos={'ordem': ['Este campo e obrigatorio.']},
            )
        resultado = organizar_imagens(projeto, dados['ordem'])
    except ErroAPI as erro:
        return resposta_erro(erro)
    return JsonResponse(resultado)


@exigir_chave_api
@require_http_methods(['DELETE'])
def detalhe_imagem_api(request, projeto_id, imagem_id):
    imagem = ImagemProjeto.objects.filter(
        pk=imagem_id,
        projeto_id=projeto_id,
    ).first()
    if not imagem:
        return resposta_erro(ErroAPI(
            'Imagem nao encontrada neste projeto.',
            'nao_encontrado',
            404,
        ))
    imagem.delete()
    return HttpResponse(status=204)
