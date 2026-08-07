from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
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

    def test_recusa_formato_de_imagem_nao_permitido(self):
        with self.assertRaisesMessage(ValidationError, 'Formato inválido'):
            Projeto.objects.create(
                titulo='Projeto GIF',
                descricao='Descrição',
                capa=self.criar_imagem('animacao.gif', 'GIF'),
            )

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

    def test_exclui_capa_anterior_depois_da_troca(self):
        projeto = Projeto.objects.create(
            titulo='Projeto',
            descricao='Descrição',
            capa=self.criar_imagem('capa-antiga.png', 'PNG'),
        )
        caminho_anterior = Path(projeto.capa.path)

        projeto.capa = self.criar_imagem('capa-nova.jpg', 'JPEG')
        with self.captureOnCommitCallbacks(execute=True):
            projeto.save()

        self.assertFalse(caminho_anterior.exists())
        self.assertTrue(Path(projeto.capa.path).exists())
        self.assertTrue(projeto.capa.name.endswith('.webp'))

    def test_mantem_capa_anterior_quando_outro_projeto_a_utiliza(self):
        projeto = Projeto.objects.create(
            titulo='Primeiro projeto',
            descricao='Descrição',
            capa=self.criar_imagem('compartilhada.png', 'PNG'),
        )
        caminho_compartilhado = Path(projeto.capa.path)
        Projeto.objects.create(
            titulo='Segundo projeto',
            descricao='Descrição',
            capa=projeto.capa.name,
        )

        projeto.capa = self.criar_imagem('substituta.jpg', 'JPEG')
        with self.captureOnCommitCallbacks(execute=True):
            projeto.save()

        self.assertTrue(caminho_compartilhado.exists())


class PortfolioViewTest(TestCase):
    def setUp(self):
        self.projeto = Projeto.objects.create(
            titulo='Projeto de teste',
            descricao='Descrição completa do projeto.',
            capa='projetos/capas/teste.webp',
            url='https://example.com/',
        )

    def test_home_exibe_galeria_horizontal_e_link_do_projeto(self):
        resposta = self.client.get(reverse('index'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-horizontal-section')
        self.assertContains(resposta, 'data-project-card')
        self.assertContains(resposta, 'project-card-label')
        self.assertContains(resposta, 'cover-card-label')
        self.assertContains(resposta, 'data-section-curtain')
        self.assertContains(resposta, 'about-backdrop')
        self.assertContains(resposta, 'about-hv-bg-mobile.webp')
        self.assertNotContains(resposta, 'data-about-system')
        self.assertNotContains(resposta, 'data-theme-toggle')
        self.assertNotContains(resposta, 'cover-facts')
        self.assertContains(
            resposta,
            reverse('detalhe_projeto', args=[self.projeto.id]),
        )
        self.assertEqual(resposta.context['projeto_destaque'], self.projeto)

    def test_pagina_exclusiva_exibe_dados_do_projeto(self):
        resposta = self.client.get(
            reverse('detalhe_projeto', args=[self.projeto.id]),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.projeto.titulo)
        self.assertContains(resposta, self.projeto.descricao)
        self.assertContains(resposta, self.projeto.url)

    def test_pagina_exclusiva_retorna_404_para_projeto_inexistente(self):
        resposta = self.client.get(reverse('detalhe_projeto', args=[999]))

        self.assertEqual(resposta.status_code, 404)

    def test_rota_sobre_redireciona_para_secao_da_home(self):
        resposta = self.client.get(reverse('sobre'))

        self.assertRedirects(
            resposta,
            f'{reverse("index")}#sobre',
            fetch_redirect_response=False,
        )
