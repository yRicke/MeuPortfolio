from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, router, transaction
from django.db.models import Max, Q
from PIL import Image, ImageOps

# Create your models here.

class Projeto(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    capa = models.ImageField(upload_to='projetos/capas/', default='projetos/capas/default.png')
    url = models.URLField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
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
            self.capa = self._converter_capa_para_webp(self.capa)

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
    def _converter_capa_para_webp(capa):
        nome = f'{Path(capa.name).stem or "imagem"}.webp'
        conteudo = BytesIO()

        with Image.open(capa) as imagem:
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

    @classmethod
    def criar_projeto(cls, titulo, descricao, capa, url=None):
        maior_ordem = cls.objects.aggregate(maior=Max('ordem'))['maior']
        primeiro_projeto = maior_ordem is None
        projeto = cls(
            titulo=titulo,
            descricao=descricao,
            capa=capa,
            url=url or '',
            ordem=0 if primeiro_projeto else maior_ordem + 1,
            destaque=primeiro_projeto,
        )
        projeto.save()
        return projeto

    def atualizar_projeto(self, titulo=None, descricao=None, capa=None, url=None):
        if titulo:
            self.titulo = titulo
        if descricao:
            self.descricao = descricao
        if capa:
            self.capa = capa
        if url is not None:
            self.url = url
        self.save()
        return self

    def deletar_projeto(self):
        era_destaque = self.destaque
        self.delete()
        if era_destaque:
            proximo_destaque = type(self).objects.first()
            if proximo_destaque:
                proximo_destaque.destaque = True
                proximo_destaque.save(update_fields=('destaque',))
