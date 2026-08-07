from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import models
from PIL import Image, ImageOps

# Create your models here.

class Projeto(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    capa = models.ImageField(upload_to='projetos/capas/', default='projetos/capas/default.png')
    url = models.URLField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if self.capa and not self.capa._committed:
            self.capa = self._converter_capa_para_webp(self.capa)
        super().save(*args, **kwargs)

    @staticmethod
    def _converter_capa_para_webp(capa):
        nome = f'{Path(capa.name).stem or "imagem"}.webp'
        conteudo = BytesIO()

        with Image.open(capa) as imagem:
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
        projeto = cls(titulo=titulo, descricao=descricao, capa=capa, url=url)
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
        self.delete()
