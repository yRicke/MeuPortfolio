from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from app.models import Projeto


class ConversaoDeCapaTest(TestCase):
    def setUp(self):
        self.diretorio_de_midias = TemporaryDirectory()
        self.configuracao = self.settings(MEDIA_ROOT=self.diretorio_de_midias.name)
        self.configuracao.enable()

    def tearDown(self):
        self.configuracao.disable()
        self.diretorio_de_midias.cleanup()

    @staticmethod
    def criar_imagem(nome, formato, modo='RGB', cor='red'):
        conteudo = BytesIO()
        Image.new(modo, (20, 10), cor).save(conteudo, format=formato)
        return SimpleUploadedFile(
            nome,
            conteudo.getvalue(),
            content_type=f'image/{formato.lower()}',
        )

    def test_converte_imagem_enviada_para_webp(self):
        projeto = Projeto.objects.create(
            titulo='Projeto JPEG',
            descricao='Descrição',
            capa=self.criar_imagem('Minha Capa.jpg', 'JPEG'),
        )

        self.assertTrue(projeto.capa.name.endswith('.webp'))
        self.assertFalse(projeto.capa.name.endswith('.jpg'))

        with Image.open(projeto.capa.path) as imagem_salva:
            self.assertEqual(imagem_salva.format, 'WEBP')
            self.assertEqual(imagem_salva.size, (20, 10))

    def test_preserva_transparencia_da_imagem(self):
        projeto = Projeto.objects.create(
            titulo='Projeto PNG',
            descricao='Descrição',
            capa=self.criar_imagem(
                'transparente.png',
                'PNG',
                modo='RGBA',
                cor=(255, 0, 0, 80),
            ),
        )

        with Image.open(projeto.capa.path) as imagem_salva:
            self.assertEqual(imagem_salva.mode, 'RGBA')
            self.assertEqual(imagem_salva.getpixel((0, 0))[3], 80)

    def test_nao_reprocessa_capa_ao_atualizar_outros_campos(self):
        projeto = Projeto.objects.create(
            titulo='Projeto',
            descricao='Descrição',
            capa=self.criar_imagem('capa.png', 'PNG'),
        )
        nome_original = projeto.capa.name
        arquivos_antes = list(Path(self.diretorio_de_midias.name).rglob('*'))

        projeto.titulo = 'Projeto atualizado'
        projeto.save()

        self.assertEqual(projeto.capa.name, nome_original)
        self.assertEqual(
            list(Path(self.diretorio_de_midias.name).rglob('*')),
            arquivos_antes,
        )
