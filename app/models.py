import hashlib
import hmac
import secrets
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, router, transaction
from django.db.models import Max, Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from PIL import Image, ImageOps

# Create your models here.

NAO_INFORMADO = object()


class ChaveAPI(models.Model):
    identificador = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    hash_chave = models.CharField(max_length=64, editable=False)
    prefixo = models.CharField(max_length=20, editable=False)
    data_rotacao = models.DateTimeField(auto_now=True)
    rotacionada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(identificador=1),
                name='app_chave_api_identificador_unico',
            ),
        ]
        verbose_name = 'chave da API'
        verbose_name_plural = 'chaves da API'

    def __str__(self):
        return f'{self.prefixo}...'

    @staticmethod
    def _calcular_hash(chave):
        return hashlib.sha256(chave.encode('utf-8')).hexdigest()

    @classmethod
    def rotacionar(cls, usuario):
        chave = f'portfolio_{secrets.token_urlsafe(32)}'
        credencial, _ = cls.objects.update_or_create(
            identificador=1,
            defaults={
                'hash_chave': cls._calcular_hash(chave),
                'prefixo': chave[:20],
                'rotacionada_por': usuario,
            },
        )
        return credencial, chave

    @classmethod
    def autenticar(cls, chave):
        if not chave:
            return False

        hash_esperado = cls.objects.filter(identificador=1).values_list(
            'hash_chave',
            flat=True,
        ).first()
        if not hash_esperado:
            return False

        return hmac.compare_digest(
            hash_esperado,
            cls._calcular_hash(chave),
        )


class ArquivoMidia(models.Model):
    nome = models.CharField(max_length=500, unique=True)
    conteudo = models.BinaryField(editable=False)
    tipo_conteudo = models.CharField(
        max_length=255,
        default='application/octet-stream',
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('nome',)
        verbose_name = 'arquivo de mídia'
        verbose_name_plural = 'arquivos de mídia'

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    capa = models.ImageField(upload_to='projetos/capas/', default='projetos/capas/default.png')
    url = models.URLField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_desenvolvimento = models.DateField(blank=True, null=True)
    ordem = models.PositiveIntegerField(default=0, db_index=True)
    destaque = models.BooleanField(default=False)

    class Meta:
        ordering = ('ordem', '-data_criacao', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=('destaque',),
                condition=Q(destaque=True),
                name='app_projeto_apenas_um_destaque',
            ),
        ]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        banco = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        campos_atualizados = kwargs.get('update_fields')
        deve_salvar_capa = campos_atualizados is None or 'capa' in campos_atualizados
        nova_capa = deve_salvar_capa and self.capa and not self.capa._committed
        capa_anterior = None

        if nova_capa and self.pk:
            capa_anterior = (
                type(self).objects.using(banco).filter(pk=self.pk)
                .values_list('capa', flat=True)
                .first()
            )

        if nova_capa:
            self.capa = self._converter_imagem_para_webp(self.capa)

        super().save(*args, **kwargs)

        if capa_anterior and capa_anterior != self.capa.name:
            modelo = type(self)
            armazenamento = self.capa.storage
            transaction.on_commit(
                lambda: modelo._excluir_capa_sem_uso(
                    capa_anterior,
                    armazenamento,
                    banco,
                ),
                using=banco,
            )

    @classmethod
    def _excluir_capa_sem_uso(cls, nome, armazenamento, banco):
        capa_padrao = cls._meta.get_field('capa').default
        ainda_esta_em_uso = cls.objects.using(banco).filter(capa=nome).exists()

        if nome != capa_padrao and not ainda_esta_em_uso:
            armazenamento.delete(nome)

    @staticmethod
    def _converter_imagem_para_webp(arquivo):
        nome = f'{Path(arquivo.name).stem or "imagem"}.webp'
        conteudo = BytesIO()

        with Image.open(arquivo) as imagem:
            if imagem.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValidationError(
                    'Formato inválido. Envie uma imagem PNG, JPEG ou WebP.'
                )

            imagem = ImageOps.exif_transpose(imagem)
            possui_transparencia = (
                imagem.mode in ('RGBA', 'LA')
                or imagem.mode == 'P' and 'transparency' in imagem.info
            )
            modo = 'RGBA' if possui_transparencia else 'RGB'
            imagem.convert(modo).save(
                conteudo,
                format='WEBP',
                quality=85,
                method=6,
            )

        return ContentFile(conteudo.getvalue(), name=nome)

    _converter_capa_para_webp = _converter_imagem_para_webp

    @classmethod
    def criar_projeto(
        cls,
        titulo,
        descricao,
        capa,
        url=None,
        data_desenvolvimento=None,
    ):
        maior_ordem = cls.objects.aggregate(maior=Max('ordem'))['maior']
        primeiro_projeto = maior_ordem is None
        projeto = cls(
            titulo=titulo,
            descricao=descricao,
            capa=capa,
            url=url or '',
            data_desenvolvimento=data_desenvolvimento,
            ordem=0 if primeiro_projeto else maior_ordem + 1,
            destaque=primeiro_projeto,
        )
        projeto.save()
        return projeto

    def atualizar_projeto(
        self,
        titulo=None,
        descricao=None,
        capa=None,
        url=None,
        data_desenvolvimento=NAO_INFORMADO,
    ):
        if titulo:
            self.titulo = titulo
        if descricao:
            self.descricao = descricao
        if capa:
            self.capa = capa
        if url is not None:
            self.url = url
        if data_desenvolvimento is not NAO_INFORMADO:
            self.data_desenvolvimento = data_desenvolvimento
        self.save()
        return self

    def adicionar_imagens(self, arquivos):
        maior_ordem = self.imagens.aggregate(maior=Max('ordem'))['maior']
        proxima_ordem = 0 if maior_ordem is None else maior_ordem + 1
        imagens = []

        for deslocamento, arquivo in enumerate(arquivos):
            imagens.append(
                ImagemProjeto.objects.create(
                    projeto=self,
                    imagem=arquivo,
                    ordem=proxima_ordem + deslocamento,
                )
            )

        return imagens

    def deletar_projeto(self):
        era_destaque = self.destaque
        self.delete()
        if era_destaque:
            proximo_destaque = type(self).objects.first()
            if proximo_destaque:
                proximo_destaque.destaque = True
                proximo_destaque.save(update_fields=('destaque',))


class ImagemProjeto(models.Model):
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='imagens',
    )
    imagem = models.ImageField(upload_to='projetos/galeria/')
    ordem = models.PositiveIntegerField(default=0)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('ordem', 'pk')

    def __str__(self):
        return f'{self.projeto.titulo} — imagem {self.ordem + 1}'

    def save(self, *args, **kwargs):
        banco = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        campos_atualizados = kwargs.get('update_fields')
        deve_salvar_imagem = (
            campos_atualizados is None or 'imagem' in campos_atualizados
        )
        nova_imagem = deve_salvar_imagem and self.imagem and not self.imagem._committed
        imagem_anterior = None

        if nova_imagem and self.pk:
            imagem_anterior = (
                type(self).objects.using(banco).filter(pk=self.pk)
                .values_list('imagem', flat=True)
                .first()
            )

        if nova_imagem:
            self.imagem = Projeto._converter_imagem_para_webp(self.imagem)

        super().save(*args, **kwargs)

        if imagem_anterior and imagem_anterior != self.imagem.name:
            armazenamento = self.imagem.storage
            transaction.on_commit(
                lambda: type(self)._excluir_imagem_sem_uso(
                    imagem_anterior,
                    armazenamento,
                    banco,
                ),
                using=banco,
            )

    @classmethod
    def _excluir_imagem_sem_uso(cls, nome, armazenamento, banco):
        ainda_esta_em_uso = cls.objects.using(banco).filter(imagem=nome).exists()
        if nome and not ainda_esta_em_uso:
            armazenamento.delete(nome)


@receiver(post_delete, sender=ImagemProjeto)
def excluir_arquivo_da_imagem(sender, instance, using, **kwargs):
    if not instance.imagem or not instance.imagem.name:
        return

    nome = instance.imagem.name
    armazenamento = instance.imagem.storage
    transaction.on_commit(
        lambda: sender._excluir_imagem_sem_uso(nome, armazenamento, using),
        using=using,
    )


@receiver(post_delete, sender=Projeto)
def excluir_arquivo_da_capa(sender, instance, using, **kwargs):
    if not instance.capa or not instance.capa.name:
        return

    nome = instance.capa.name
    armazenamento = instance.capa.storage
    transaction.on_commit(
        lambda: sender._excluir_capa_sem_uso(nome, armazenamento, using),
        using=using,
    )
