import base64
import binascii
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Max

from app.models import ImagemProjeto, Projeto


class ErroAPI(Exception):
    def __init__(self, mensagem, codigo='dados_invalidos', status=400, campos=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.status = status
        self.campos = campos or {}


def serializar_imagem(imagem, request=None):
    url = imagem.imagem.url
    if request:
        url = request.build_absolute_uri(url)
    return {
        'id': imagem.pk,
        'url': url,
        'ordem': imagem.ordem,
        'data_criacao': imagem.data_criacao.isoformat(),
    }


def serializar_projeto(projeto, request=None):
    capa_url = projeto.capa.url if projeto.capa else None
    if request and capa_url:
        capa_url = request.build_absolute_uri(capa_url)

    return {
        'id': projeto.pk,
        'titulo': projeto.titulo,
        'descricao': projeto.descricao,
        'capa_url': capa_url,
        'url': projeto.url,
        'data_criacao': projeto.data_criacao.isoformat(),
        'data_desenvolvimento': (
            projeto.data_desenvolvimento.isoformat()
            if projeto.data_desenvolvimento
            else None
        ),
        'ordem': projeto.ordem,
        'destaque': projeto.destaque,
        'imagens': [
            serializar_imagem(imagem, request)
            for imagem in projeto.imagens.all()
        ],
    }


def interpretar_data(valor):
    if valor in (None, ''):
        return None
    if not isinstance(valor, str):
        raise ErroAPI(
            'A data de desenvolvimento deve ser uma string.',
            campos={'data_desenvolvimento': ['Use AAAA-MM ou AAAA-MM-DD.']},
        )

    for formato in ('%Y-%m-%d', '%Y-%m'):
        try:
            return datetime.strptime(valor, formato).date().replace(day=1)
        except ValueError:
            pass
    raise ErroAPI(
        'A data de desenvolvimento e invalida.',
        campos={'data_desenvolvimento': ['Use AAAA-MM ou AAAA-MM-DD.']},
    )


def decodificar_arquivo(dado, campo):
    if dado is None:
        return None
    if not isinstance(dado, dict):
        raise ErroAPI(
            f'O campo {campo} deve conter nome e conteudo_base64.',
            campos={campo: ['Formato de arquivo invalido.']},
        )

    nome = dado.get('nome')
    conteudo = dado.get('conteudo_base64')
    if not isinstance(nome, str) or not nome.strip() or not isinstance(conteudo, str):
        raise ErroAPI(
            f'O campo {campo} deve conter nome e conteudo_base64.',
            campos={campo: ['Nome e conteudo_base64 sao obrigatorios.']},
        )
    try:
        binario = base64.b64decode(conteudo, validate=True)
    except (ValueError, binascii.Error):
        raise ErroAPI(
            f'O conteudo de {campo} nao e um base64 valido.',
            campos={campo: ['Base64 invalido.']},
        ) from None
    if len(binario) > 10 * 1024 * 1024:
        raise ErroAPI(
            f'O arquivo de {campo} excede 10 MB.',
            campos={campo: ['O limite por imagem e 10 MB.']},
        )
    return ContentFile(binario, name=nome.strip())


def decodificar_imagens(dados):
    if dados in (None, ''):
        return []
    if not isinstance(dados, list):
        raise ErroAPI(
            'O campo imagens deve ser uma lista.',
            campos={'imagens': ['Envie uma lista de arquivos.']},
        )
    return [decodificar_arquivo(item, 'imagens') for item in dados]


def _validar_texto(dados, campo, obrigatorio=False):
    if campo not in dados:
        if obrigatorio:
            raise ErroAPI(
                f'O campo {campo} e obrigatorio.',
                campos={campo: ['Este campo e obrigatorio.']},
            )
        return None
    valor = dados[campo]
    if not isinstance(valor, str) or not valor.strip():
        raise ErroAPI(
            f'O campo {campo} nao pode ficar vazio.',
            campos={campo: ['Este campo nao pode ficar vazio.']},
        )
    return valor.strip()


def _validar_url(dados):
    if 'url' not in dados:
        return None
    valor = dados['url']
    if valor in (None, ''):
        return ''
    if not isinstance(valor, str):
        raise ErroAPI('A URL e invalida.', campos={'url': ['Informe uma URL valida.']})
    valor = valor.strip()
    try:
        URLValidator(schemes=('http', 'https'))(valor)
    except ValidationError:
        raise ErroAPI(
            'A URL e invalida.',
            campos={'url': ['Informe uma URL HTTP ou HTTPS valida.']},
        ) from None
    return valor


def criar_projeto(dados, capa=None, imagens=None):
    titulo = _validar_texto(dados, 'titulo', obrigatorio=True)
    descricao = _validar_texto(dados, 'descricao', obrigatorio=True)
    url = _validar_url(dados)
    data_desenvolvimento = interpretar_data(dados.get('data_desenvolvimento'))
    imagens = imagens or []

    try:
        with transaction.atomic():
            projetos = Projeto.objects.select_for_update()
            maior_ordem = projetos.aggregate(maior=Max('ordem'))['maior']
            projeto = Projeto(
                titulo=titulo,
                descricao=descricao,
                url=url or '',
                data_desenvolvimento=data_desenvolvimento,
                ordem=0 if maior_ordem is None else maior_ordem + 1,
                destaque=maior_ordem is None,
            )
            if capa:
                projeto.capa = capa
            projeto.full_clean()
            projeto.save()
            projeto.adicionar_imagens(imagens)
    except ValidationError as erro:
        raise ErroAPI(
            'Nao foi possivel validar o projeto.',
            campos=getattr(erro, 'message_dict', {'dados': erro.messages}),
        ) from None
    except OSError:
        raise ErroAPI(
            'Uma das imagens enviadas e invalida.',
            codigo='imagem_invalida',
            campos={'imagens': ['Envie arquivos PNG, JPEG ou WebP validos.']},
        ) from None

    return Projeto.objects.prefetch_related('imagens').get(pk=projeto.pk)


def atualizar_projeto(projeto, dados, capa=None, imagens=None, substituir=False):
    titulo = _validar_texto(dados, 'titulo', obrigatorio=substituir)
    descricao = _validar_texto(dados, 'descricao', obrigatorio=substituir)
    url = _validar_url(dados)

    if titulo is not None:
        projeto.titulo = titulo
    if descricao is not None:
        projeto.descricao = descricao
    if substituir:
        projeto.url = url or ''
    elif 'url' in dados:
        projeto.url = url
    if substituir:
        projeto.data_desenvolvimento = interpretar_data(
            dados.get('data_desenvolvimento')
        )
    elif 'data_desenvolvimento' in dados:
        projeto.data_desenvolvimento = interpretar_data(
            dados.get('data_desenvolvimento')
        )
    if capa:
        projeto.capa = capa

    try:
        with transaction.atomic():
            projeto.full_clean()
            projeto.save()
            if imagens:
                projeto.adicionar_imagens(imagens)
    except ValidationError as erro:
        raise ErroAPI(
            'Nao foi possivel validar o projeto.',
            campos=getattr(erro, 'message_dict', {'dados': erro.messages}),
        ) from None
    except OSError:
        raise ErroAPI(
            'Uma das imagens enviadas e invalida.',
            codigo='imagem_invalida',
            campos={'imagens': ['Envie arquivos PNG, JPEG ou WebP validos.']},
        ) from None

    return Projeto.objects.prefetch_related('imagens').get(pk=projeto.pk)


def organizar_projetos(ordem, destaque):
    try:
        ordem = [int(projeto_id) for projeto_id in ordem]
        destaque = int(destaque) if destaque is not None else None
    except (TypeError, ValueError):
        raise ErroAPI('A ordem ou o destaque e invalido.') from None
    if len(ordem) != len(set(ordem)):
        raise ErroAPI('A ordem contem projetos repetidos.')

    with transaction.atomic():
        projetos = list(Projeto.objects.select_for_update())
        projetos_por_id = {projeto.pk: projeto for projeto in projetos}
        if set(ordem) != set(projetos_por_id):
            raise ErroAPI('A lista de projetos esta incompleta ou desatualizada.')
        if ordem and destaque not in projetos_por_id:
            raise ErroAPI('Escolha um projeto em destaque.')
        if not ordem and destaque is not None:
            raise ErroAPI('O destaque deve ser nulo quando nao ha projetos.')

        Projeto.objects.filter(destaque=True).update(destaque=False)
        for posicao, projeto_id in enumerate(ordem):
            projetos_por_id[projeto_id].ordem = posicao
        if projetos:
            Projeto.objects.bulk_update(projetos, ('ordem',))
            Projeto.objects.filter(pk=destaque).update(destaque=True)

    return {'ordem': ordem, 'destaque': destaque}


def organizar_imagens(projeto, ordem):
    try:
        ordem = [int(imagem_id) for imagem_id in ordem]
    except (TypeError, ValueError):
        raise ErroAPI('A ordem das imagens e invalida.') from None
    if len(ordem) != len(set(ordem)):
        raise ErroAPI('A ordem contem imagens repetidas.')

    with transaction.atomic():
        imagens = list(projeto.imagens.select_for_update())
        imagens_por_id = {imagem.pk: imagem for imagem in imagens}
        if set(ordem) != set(imagens_por_id):
            raise ErroAPI('A lista de imagens esta incompleta ou desatualizada.')
        for posicao, imagem_id in enumerate(ordem):
            imagens_por_id[imagem_id].ordem = posicao
        if imagens:
            ImagemProjeto.objects.bulk_update(imagens, ('ordem',))

    return {'projeto_id': projeto.pk, 'ordem': ordem}
