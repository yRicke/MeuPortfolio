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


SCHEMA_ARQUIVO = {
    'type': 'object',
    'description': 'Imagem PNG, JPEG ou WebP codificada em base64 (limite de 10 MB).',
    'properties': {
        'nome': {'type': 'string', 'description': 'Nome do arquivo com extensao.'},
        'conteudo_base64': {'type': 'string', 'description': 'Conteudo base64 puro.'},
    },
    'required': ['nome', 'conteudo_base64'],
    'additionalProperties': False,
}


FERRAMENTAS = [
    {
        'name': 'listar_projetos',
        'description': 'Lista todos os projetos do portfolio na ordem de exibicao.',
        'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        'annotations': {'readOnlyHint': True, 'openWorldHint': False},
    },
    {
        'name': 'obter_projeto',
        'description': 'Obtem um projeto e todas as imagens de sua galeria.',
        'inputSchema': {
            'type': 'object',
            'properties': {'projeto_id': {'type': 'integer', 'minimum': 1}},
            'required': ['projeto_id'],
            'additionalProperties': False,
        },
        'annotations': {'readOnlyHint': True, 'openWorldHint': False},
    },
    {
        'name': 'criar_projeto',
        'description': 'Cria um projeto; aceita capa e imagens da galeria em base64.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'titulo': {'type': 'string', 'minLength': 1, 'maxLength': 200},
                'descricao': {'type': 'string', 'minLength': 1},
                'url': {'type': 'string'},
                'data_desenvolvimento': {
                    'type': ['string', 'null'],
                    'description': 'Data no formato AAAA-MM ou AAAA-MM-DD.',
                },
                'capa': SCHEMA_ARQUIVO,
                'imagens': {'type': 'array', 'items': SCHEMA_ARQUIVO},
            },
            'required': ['titulo', 'descricao'],
            'additionalProperties': False,
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'openWorldHint': False},
    },
    {
        'name': 'atualizar_projeto',
        'description': 'Atualiza somente os campos informados e pode adicionar novas imagens.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'projeto_id': {'type': 'integer', 'minimum': 1},
                'titulo': {'type': 'string', 'minLength': 1, 'maxLength': 200},
                'descricao': {'type': 'string', 'minLength': 1},
                'url': {'type': ['string', 'null']},
                'data_desenvolvimento': {'type': ['string', 'null']},
                'capa': SCHEMA_ARQUIVO,
                'imagens': {'type': 'array', 'items': SCHEMA_ARQUIVO},
            },
            'required': ['projeto_id'],
            'additionalProperties': False,
        },
        'annotations': {
            'readOnlyHint': False,
            'destructiveHint': False,
            'idempotentHint': True,
            'openWorldHint': False,
        },
    },
    {
        'name': 'excluir_projeto',
        'description': 'Exclui permanentemente um projeto e sua galeria.',
        'inputSchema': {
            'type': 'object',
            'properties': {'projeto_id': {'type': 'integer', 'minimum': 1}},
            'required': ['projeto_id'],
            'additionalProperties': False,
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': True, 'openWorldHint': False},
    },
    {
        'name': 'adicionar_imagens_projeto',
        'description': 'Adiciona uma ou mais imagens ao final da galeria de um projeto.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'projeto_id': {'type': 'integer', 'minimum': 1},
                'imagens': {'type': 'array', 'minItems': 1, 'items': SCHEMA_ARQUIVO},
            },
            'required': ['projeto_id', 'imagens'],
            'additionalProperties': False,
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'openWorldHint': False},
    },
    {
        'name': 'excluir_imagem_projeto',
        'description': 'Exclui permanentemente uma imagem da galeria de um projeto.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'projeto_id': {'type': 'integer', 'minimum': 1},
                'imagem_id': {'type': 'integer', 'minimum': 1},
            },
            'required': ['projeto_id', 'imagem_id'],
            'additionalProperties': False,
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': True, 'openWorldHint': False},
    },
    {
        'name': 'organizar_projetos',
        'description': 'Define a ordem completa dos projetos e qual deles e o destaque.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'ordem': {'type': 'array', 'items': {'type': 'integer'}},
                'destaque': {'type': ['integer', 'null']},
            },
            'required': ['ordem', 'destaque'],
            'additionalProperties': False,
        },
        'annotations': {
            'readOnlyHint': False,
            'destructiveHint': False,
            'idempotentHint': True,
            'openWorldHint': False,
        },
    },
    {
        'name': 'organizar_imagens_projeto',
        'description': 'Define a ordem completa das imagens da galeria de um projeto.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'projeto_id': {'type': 'integer', 'minimum': 1},
                'ordem': {'type': 'array', 'items': {'type': 'integer'}},
            },
            'required': ['projeto_id', 'ordem'],
            'additionalProperties': False,
        },
        'annotations': {
            'readOnlyHint': False,
            'destructiveHint': False,
            'idempotentHint': True,
            'openWorldHint': False,
        },
    },
]


def _buscar_projeto(projeto_id):
    projeto = Projeto.objects.prefetch_related('imagens').filter(pk=projeto_id).first()
    if not projeto:
        raise ErroAPI('Projeto nao encontrado.', 'nao_encontrado', 404)
    return projeto


def _executar_ferramenta(nome, argumentos, request):
    if not isinstance(argumentos, dict):
        raise ErroAPI('Os argumentos da ferramenta devem formar um objeto.')

    if nome == 'listar_projetos':
        projetos = Projeto.objects.prefetch_related('imagens')
        return {
            'projetos': [serializar_projeto(item, request) for item in projetos],
            'total': projetos.count(),
        }
    if nome == 'obter_projeto':
        return {'projeto': serializar_projeto(
            _buscar_projeto(argumentos.get('projeto_id')),
            request,
        )}
    if nome == 'criar_projeto':
        projeto = criar_projeto(
            argumentos,
            decodificar_arquivo(argumentos.get('capa'), 'capa'),
            decodificar_imagens(argumentos.get('imagens')),
        )
        return {'projeto': serializar_projeto(projeto, request)}
    if nome == 'atualizar_projeto':
        projeto = atualizar_projeto(
            _buscar_projeto(argumentos.get('projeto_id')),
            argumentos,
            decodificar_arquivo(argumentos.get('capa'), 'capa'),
            decodificar_imagens(argumentos.get('imagens')),
        )
        return {'projeto': serializar_projeto(projeto, request)}
    if nome == 'excluir_projeto':
        projeto = _buscar_projeto(argumentos.get('projeto_id'))
        projeto_id = projeto.pk
        projeto.deletar_projeto()
        return {'excluido': True, 'projeto_id': projeto_id}
    if nome == 'adicionar_imagens_projeto':
        projeto = _buscar_projeto(argumentos.get('projeto_id'))
        imagens = decodificar_imagens(argumentos.get('imagens'))
        if not imagens:
            raise ErroAPI('Envie ao menos uma imagem.')
        adicionadas = projeto.adicionar_imagens(imagens)
        return {'imagens': [serializar_imagem(item, request) for item in adicionadas]}
    if nome == 'excluir_imagem_projeto':
        imagem = ImagemProjeto.objects.filter(
            pk=argumentos.get('imagem_id'),
            projeto_id=argumentos.get('projeto_id'),
        ).first()
        if not imagem:
            raise ErroAPI(
                'Imagem nao encontrada neste projeto.',
                'nao_encontrado',
                404,
            )
        imagem_id = imagem.pk
        imagem.delete()
        return {'excluida': True, 'imagem_id': imagem_id}
    if nome == 'organizar_projetos':
        return organizar_projetos(
            argumentos.get('ordem'),
            argumentos.get('destaque'),
        )
    if nome == 'organizar_imagens_projeto':
        return organizar_imagens(
            _buscar_projeto(argumentos.get('projeto_id')),
            argumentos.get('ordem'),
        )
    raise ErroAPI(f'Ferramenta desconhecida: {nome}.', 'ferramenta_inexistente', 404)


def _resultado_ferramenta(resultado):
    return {
        'content': [{
            'type': 'text',
            'text': json.dumps(resultado, ensure_ascii=False),
        }],
        'structuredContent': resultado,
        'isError': False,
    }


def _erro_ferramenta(erro):
    dados = {'codigo': erro.codigo, 'mensagem': erro.mensagem}
    if erro.campos:
        dados['campos'] = erro.campos
    return {
        'content': [{
            'type': 'text',
            'text': json.dumps({'erro': dados}, ensure_ascii=False),
        }],
        'isError': True,
    }


def _resposta_jsonrpc(identificador, resultado=None, erro=None):
    resposta = {'jsonrpc': '2.0', 'id': identificador}
    if erro:
        resposta['error'] = erro
    else:
        resposta['result'] = resultado
    return JsonResponse(resposta)


@exigir_chave_api
@require_http_methods(['POST'])
def endpoint_mcp(request):
    try:
        mensagem = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return _resposta_jsonrpc(None, erro={
            'code': -32700,
            'message': 'JSON invalido.',
        })
    if not isinstance(mensagem, dict):
        return _resposta_jsonrpc(None, erro={
            'code': -32600,
            'message': 'Requisicao JSON-RPC invalida.',
        })

    identificador = mensagem.get('id')
    metodo = mensagem.get('method')
    parametros = mensagem.get('params') or {}

    if identificador is None:
        return HttpResponse(status=202)
    if metodo == 'initialize':
        versao = parametros.get('protocolVersion', '2025-06-18')
        return _resposta_jsonrpc(identificador, {
            'protocolVersion': versao,
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': {'name': 'portfolio-projetos', 'version': '1.0.0'},
            'instructions': (
                'Gerencie os projetos do portfolio por estas ferramentas. Antes de '
                'alterar ou excluir, liste ou obtenha o projeto para confirmar IDs e '
                'estado atual. Ordem de projetos e de imagens sempre deve conter todos '
                'os IDs atuais, sem repeticao. Imagens aceitam PNG, JPEG ou WebP em base64.'
            ),
        })
    if metodo == 'ping':
        return _resposta_jsonrpc(identificador, {})
    if metodo == 'tools/list':
        return _resposta_jsonrpc(identificador, {'tools': FERRAMENTAS})
    if metodo == 'tools/call':
        try:
            resultado = _executar_ferramenta(
                parametros.get('name'),
                parametros.get('arguments') or {},
                request,
            )
            conteudo = _resultado_ferramenta(resultado)
        except ErroAPI as erro:
            conteudo = _erro_ferramenta(erro)
        except (OSError, ValidationError, ValueError):
            conteudo = _erro_ferramenta(ErroAPI(
                'Uma das imagens ou valores enviados e invalido.',
                'dados_invalidos',
            ))
        return _resposta_jsonrpc(identificador, conteudo)
    return _resposta_jsonrpc(identificador, erro={
        'code': -32601,
        'message': f'Metodo nao encontrado: {metodo}.',
    })
