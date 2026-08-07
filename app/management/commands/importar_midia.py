import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import ArquivoMidia, ImagemProjeto, Projeto


class Command(BaseCommand):
    help = 'Importa para o banco os arquivos de mídia referenciados pelos projetos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--origem',
            default=str(settings.MEDIA_ROOT),
            help='Diretório local que contém os arquivos de mídia.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        origem = Path(options['origem']).resolve()
        nomes = {
            nome
            for nome in Projeto.objects.values_list('capa', flat=True)
            if nome
        }
        nomes.update(
            nome
            for nome in ImagemProjeto.objects.values_list('imagem', flat=True)
            if nome
        )

        ausentes = []
        importados = 0
        for nome in sorted(nomes):
            caminho = (origem / nome).resolve()
            if not caminho.is_relative_to(origem) or not caminho.is_file():
                ausentes.append(nome)
                continue

            ArquivoMidia.objects.update_or_create(
                nome=nome,
                defaults={
                    'conteudo': caminho.read_bytes(),
                    'tipo_conteudo': (
                        mimetypes.guess_type(nome)[0]
                        or 'application/octet-stream'
                    ),
                },
            )
            importados += 1

        if ausentes:
            raise CommandError(
                'Arquivos referenciados não encontrados: '
                + ', '.join(ausentes)
            )

        self.stdout.write(self.style.SUCCESS(
            f'{importados} arquivos de mídia importados com sucesso.'
        ))
