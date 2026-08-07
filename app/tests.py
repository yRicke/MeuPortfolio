import json
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from PIL import Image

from app.models import ArquivoMidia, ImagemProjeto, Projeto
from app.storage import DatabaseStorage
from app.views import servir_midia


class DatabaseStorageTest(TestCase):
    def setUp(self):
        self.storage = DatabaseStorage()

    def test_salva_abre_serve_e_exclui_arquivo(self):
        nome = self.storage.save(
            'projetos/galeria/teste.webp',
            SimpleUploadedFile(
                'teste.webp',
                b'conteudo-webp',
                content_type='image/webp',
            ),
        )

        self.assertEqual(nome, 'projetos/galeria/teste.webp')
        self.assertTrue(self.storage.exists(nome))
        self.assertEqual(self.storage.size(nome), len(b'conteudo-webp'))
        with self.storage.open(nome) as arquivo:
            self.assertEqual(arquivo.read(), b'conteudo-webp')

        resposta = servir_midia(
            RequestFactory().get(self.storage.url(nome)),
            nome,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b'conteudo-webp')
        self.assertEqual(resposta['Content-Type'], 'image/webp')
        self.assertIn('immutable', resposta['Cache-Control'])

        self.storage.delete(nome)
        self.assertFalse(ArquivoMidia.objects.filter(nome=nome).exists())


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

    def test_converte_imagens_adicionais_para_webp_e_preserva_ordem(self):
        projeto = Projeto.objects.create(
            titulo='Projeto com galeria',
            descricao='Descrição',
            capa=self.criar_imagem('capa.png', 'PNG'),
        )

        imagens = projeto.adicionar_imagens([
            self.criar_imagem('primeira.jpg', 'JPEG'),
            self.criar_imagem('segunda.png', 'PNG'),
        ])

        self.assertEqual([item.ordem for item in imagens], [0, 1])
        self.assertEqual(projeto.imagens.count(), 2)
        for item in imagens:
            self.assertTrue(item.imagem.name.endswith('.webp'))
            with Image.open(item.imagem.path) as imagem_salva:
                self.assertEqual(imagem_salva.format, 'WEBP')

    def test_exclui_arquivo_quando_imagem_adicional_e_removida(self):
        projeto = Projeto.objects.create(
            titulo='Projeto com galeria',
            descricao='Descrição',
            capa=self.criar_imagem('capa.png', 'PNG'),
        )
        imagem = projeto.adicionar_imagens([
            self.criar_imagem('galeria.png', 'PNG'),
        ])[0]
        caminho = Path(imagem.imagem.path)

        with self.captureOnCommitCallbacks(execute=True):
            imagem.delete()

        self.assertFalse(caminho.exists())


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
        self.assertContains(resposta, 'favicon.ico')
        self.assertContains(resposta, 'favicon.png', count=2)
        self.assertContains(resposta, 'projects-end-arrow')
        self.assertContains(
            resposta,
            'mailto:henriquevieiraperes@gmail.com?subject=Novo%20projeto',
        )
        self.assertContains(
            resposta,
            'Entrar em contato para criar o próximo projeto',
        )
        self.assertContains(resposta, 'cover-art-link')
        self.assertContains(
            resposta,
            f'Abrir projeto em destaque: {self.projeto.titulo}',
        )
        self.assertNotContains(resposta, '<i>↘</i>', html=True)
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

    def test_pagina_exclusiva_exibe_carrossel_manual_no_cabecalho_e_data(self):
        self.projeto.data_desenvolvimento = date(2025, 8, 1)
        self.projeto.save(update_fields=('data_desenvolvimento',))
        ImagemProjeto.objects.create(
            projeto=self.projeto,
            imagem='projetos/galeria/primeira.webp',
            ordem=0,
        )
        ImagemProjeto.objects.create(
            projeto=self.projeto,
            imagem='projetos/galeria/segunda.webp',
            ordem=1,
        )

        resposta = self.client.get(
            reverse('detalhe_projeto', args=[self.projeto.id]),
        )

        self.assertContains(resposta, 'data-project-carousel')
        self.assertContains(resposta, 'data-project-slide', count=2)
        self.assertContains(resposta, 'project-detail-hero-chrome')
        self.assertContains(resposta, 'data-project-carousel-controls')
        self.assertContains(resposta, 'data-project-carousel-previous')
        self.assertContains(resposta, 'data-project-carousel-next')
        self.assertContains(resposta, 'projetos/galeria/primeira.webp', count=1)
        self.assertContains(resposta, 'projetos/galeria/segunda.webp', count=1)
        self.assertNotContains(resposta, self.projeto.capa.url)
        self.assertNotContains(resposta, 'project-gallery')
        self.assertNotContains(resposta, 'project-detail-slide-label')
        self.assertContains(resposta, 'project-detail-overview')
        self.assertContains(resposta, 'project-detail-signature')
        self.assertContains(resposta, 'project-detail-signature-logo')
        self.assertContains(resposta, 'project-detail-next-footer')
        self.assertContains(resposta, 'datetime="2025-08"')
        self.assertContains(resposta, 'Desenvolvido em')

    def test_pagina_exclusiva_sem_imagens_nao_exibe_controles(self):
        resposta = self.client.get(
            reverse('detalhe_projeto', args=[self.projeto.id]),
        )

        self.assertContains(resposta, 'data-project-slide', count=1)
        self.assertNotContains(resposta, 'data-project-carousel-controls')
        self.assertNotContains(resposta, self.projeto.capa.url)

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


class PainelProjetosTest(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.superusuario = usuario.objects.create_superuser(
            username='administrador',
            password='senha-segura',
        )
        self.usuario_comum = usuario.objects.create_user(
            username='editor',
            password='senha-segura',
        )
        self.projetos = [
            Projeto.objects.create(
                titulo=f'Projeto {indice}',
                descricao='Descrição',
                capa=f'projetos/capas/projeto-{indice}.webp',
                ordem=indice - 1,
                destaque=indice == 1,
            )
            for indice in range(1, 4)
        ]

    def test_painel_exige_superusuario(self):
        resposta_anonima = self.client.get(reverse('painel_projetos'))

        self.assertRedirects(
            resposta_anonima,
            f'{reverse("entrar")}?next={reverse("painel_projetos")}',
            fetch_redirect_response=False,
        )

        self.client.force_login(self.usuario_comum)
        resposta_sem_permissao = self.client.get(reverse('painel_projetos'))

        self.assertEqual(resposta_sem_permissao.status_code, 403)

    def test_painel_exibe_organizador_para_superusuario(self):
        self.client.force_login(self.superusuario)
        resposta = self.client.get(reverse('painel_projetos'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-organizer-form')
        self.assertContains(resposta, 'data-project-list')
        self.assertContains(resposta, 'organizador-projetos.js')
        self.assertContains(resposta, 'organizer-cover-shade', count=3)
        self.assertContains(resposta, self.projetos[0].capa.url)
        self.assertContains(resposta, 'Usar como destaque', count=3)

    def test_rotas_de_edicao_exigem_superusuario(self):
        self.client.force_login(self.usuario_comum)

        self.assertEqual(
            self.client.get(reverse('adicionar_projeto')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('editar_projeto', args=[self.projetos[0].pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('deletar_projeto', args=[self.projetos[0].pk])
            ).status_code,
            403,
        )

    def test_exclusao_aceita_somente_post(self):
        self.client.force_login(self.superusuario)
        url = reverse('deletar_projeto', args=[self.projetos[2].pk])

        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Projeto.objects.filter(pk=self.projetos[2].pk).exists())

        resposta = self.client.post(url)

        self.assertRedirects(resposta, reverse('index'))
        self.assertFalse(Projeto.objects.filter(pk=self.projetos[2].pk).exists())

    def test_salva_ordem_e_projeto_em_destaque(self):
        self.client.force_login(self.superusuario)
        nova_ordem = [
            self.projetos[2].pk,
            self.projetos[0].pk,
            self.projetos[1].pk,
        ]

        resposta = self.client.post(
            reverse('painel_projetos'),
            data=json.dumps({
                'ordem': nova_ordem,
                'destaque': self.projetos[1].pk,
            }),
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            list(Projeto.objects.values_list('pk', flat=True)),
            nova_ordem,
        )
        self.assertEqual(
            Projeto.objects.get(destaque=True),
            self.projetos[1],
        )

        pagina_publica = self.client.get(reverse('index'))
        self.assertEqual(
            pagina_publica.context['projeto_destaque'],
            self.projetos[1],
        )

    def test_recusa_lista_incompleta_sem_alterar_organizacao(self):
        self.client.force_login(self.superusuario)
        ordem_original = list(Projeto.objects.values_list('pk', flat=True))

        resposta = self.client.post(
            reverse('painel_projetos'),
            data=json.dumps({
                'ordem': ordem_original[:-1],
                'destaque': self.projetos[0].pk,
            }),
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(
            list(Projeto.objects.values_list('pk', flat=True)),
            ordem_original,
        )
        self.assertEqual(Projeto.objects.get(destaque=True), self.projetos[0])

    def test_novo_projeto_entra_no_final_da_ordem(self):
        novo_projeto = Projeto.criar_projeto(
            titulo='Projeto novo',
            descricao='Descrição',
            capa='projetos/capas/projeto-novo.webp',
        )

        self.assertEqual(novo_projeto.ordem, 3)
        self.assertFalse(novo_projeto.destaque)

    def test_excluir_destaque_promove_primeiro_projeto_restante(self):
        self.projetos[0].deletar_projeto()
        self.projetos[1].refresh_from_db()

        self.assertTrue(self.projetos[1].destaque)

    def test_edicao_salva_data_e_multiplas_imagens(self):
        self.client.force_login(self.superusuario)

        with TemporaryDirectory() as diretorio:
            with self.settings(MEDIA_ROOT=diretorio):
                resposta = self.client.post(
                    reverse('editar_projeto', args=[self.projetos[0].pk]),
                    data={
                        'titulo': self.projetos[0].titulo,
                        'descricao': self.projetos[0].descricao,
                        'url': '',
                        'data_desenvolvimento': '2026-03',
                        'imagens': [
                            ConversaoDeCapaTest.criar_imagem('um.png', 'PNG'),
                            ConversaoDeCapaTest.criar_imagem('dois.jpg', 'JPEG'),
                        ],
                    },
                )

                self.assertRedirects(
                    resposta,
                    reverse('editar_projeto', args=[self.projetos[0].pk]),
                )
                self.projetos[0].refresh_from_db()
                self.assertEqual(
                    self.projetos[0].data_desenvolvimento,
                    date(2026, 3, 1),
                )
                self.assertEqual(self.projetos[0].imagens.count(), 2)
                self.assertTrue(all(
                    item.imagem.name.endswith('.webp')
                    for item in self.projetos[0].imagens.all()
                ))
