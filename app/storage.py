import mimetypes
from urllib.parse import quote

from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage


class DatabaseStorage(Storage):
    @staticmethod
    def _modelo():
        return apps.get_model('app', 'ArquivoMidia')

    def _open(self, name, mode='rb'):
        arquivo = self._modelo().objects.get(nome=name)
        return ContentFile(bytes(arquivo.conteudo), name=name)

    def _save(self, name, content):
        tipo_conteudo = getattr(content, 'content_type', None)
        if not tipo_conteudo:
            tipo_conteudo = mimetypes.guess_type(name)[0]

        self._modelo().objects.update_or_create(
            nome=name,
            defaults={
                'conteudo': b''.join(content.chunks()),
                'tipo_conteudo': tipo_conteudo or 'application/octet-stream',
            },
        )
        return name

    def delete(self, name):
        self._modelo().objects.filter(nome=name).delete()

    def exists(self, name):
        return self._modelo().objects.filter(nome=name).exists()

    def size(self, name):
        arquivo = self._modelo().objects.only('conteudo').get(nome=name)
        return len(arquivo.conteudo)

    def url(self, name):
        return f'{settings.MEDIA_URL.rstrip("/")}/{quote(name, safe="/")}'

    def get_created_time(self, name):
        return self._modelo().objects.only('data_criacao').get(
            nome=name,
        ).data_criacao
