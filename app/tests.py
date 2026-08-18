import base64
import json
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver, reverse
from PIL import Image

from app.error_views import erro_500
from app.models import ArquivoMidia, ChaveAPI, ImagemProjeto, Projeto
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


class PainelChaveAPITest(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.staff = usuario.objects.create_user(
            username='staff',
            password='senha-segura',
            is_staff=True,
        )
        self.usuario_comum = usuario.objects.create_user(
            username='comum',
            password='senha-segura',
        )

    def test_painel_e_exclusivo_para_staff(self):
        url = reverse('painel_chave_api')
        resposta = self.client.get(url)
        self.assertRedirects(
            resposta,
            f'{reverse("entrar")}?next={url}',
            fetch_redirect_response=False,
        )

        self.client.force_login(self.usuario_comum)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_rotacao_exibe_chave_uma_vez_e_armazena_somente_hash(self):
        self.client.force_login(self.staff)
        resposta = self.client.post(reverse('painel_chave_api'))

        self.assertEqual(resposta.status_code, 200)
        chave = resposta.context['nova_chave']
        credencial = ChaveAPI.objects.get()
        self.assertContains(resposta, chave)
        self.assertNotEqual(credencial.hash_chave, chave)
        self.assertNotIn(chave, credencial.hash_chave)
        self.assertTrue(ChaveAPI.autenticar(chave))
        self.assertIn('no-store', resposta['Cache-Control'])

        resposta_seguinte = self.client.get(reverse('painel_chave_api'))
        self.assertNotContains(resposta_seguinte, chave)
        self.assertContains(resposta_seguinte, f'{credencial.prefixo}...')

    def test_rotacao_invalida_chave_anterior(self):
        _, chave_anterior = ChaveAPI.rotacionar(self.staff)
        _, chave_nova = ChaveAPI.rotacionar(self.staff)

        self.assertFalse(ChaveAPI.autenticar(chave_anterior))
        self.assertTrue(ChaveAPI.autenticar(chave_nova))

    def test_login_respeita_destino_interno(self):
        pagina_login = self.client.get(
            f'{reverse("entrar")}?next={reverse("painel_chave_api")}'
        )
        self.assertContains(
            pagina_login,
            f'name="next" value="{reverse("painel_chave_api")}"',
        )

        resposta = self.client.post(reverse('entrar'), data={
            'username': self.staff.username,
            'password': 'senha-segura',
            'next': reverse('painel_chave_api'),
        })
        self.assertRedirects(
            resposta,
            reverse('painel_chave_api'),
            fetch_redirect_response=False,
        )


class APIProjetosTest(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username='staff-api',
            is_staff=True,
        )
        _, self.chave = ChaveAPI.rotacionar(usuario)
        self.autorizacao = {'HTTP_AUTHORIZATION': f'Bearer {self.chave}'}

    @staticmethod
    def imagem_base64(nome='imagem.png', cor='blue'):
        arquivo = ConversaoDeCapaTest.criar_imagem(nome, 'PNG', cor=cor)
        return {
            'nome': nome,
            'conteudo_base64': base64.b64encode(arquivo.read()).decode('ascii'),
        }

    def requisicao_json(self, metodo, url, dados=None, **headers):
        return getattr(self.client, metodo)(
            url,
            data=json.dumps(dados or {}),
            content_type='application/json',
            **self.autorizacao,
            **headers,
        )

    def criar_projeto(self, titulo='Projeto API'):
        resposta = self.requisicao_json('post', reverse('colecao_projetos_api'), {
            'titulo': titulo,
            'descricao': 'Criado por integração.',
            'url': 'https://example.com/projeto',
            'data_desenvolvimento': '2026-08',
            'capa': self.imagem_base64('capa.png'),
            'imagens': [self.imagem_base64('galeria.png', 'green')],
        })
        self.assertEqual(resposta.status_code, 201, resposta.content)
        return resposta.json()['projeto']

    def test_api_exige_bearer_token_valido(self):
        url = reverse('colecao_projetos_api')
        sem_chave = self.client.get(url)
        chave_invalida = self.client.get(
            url,
            HTTP_AUTHORIZATION='Bearer portfolio_invalida',
        )

        self.assertEqual(sem_chave.status_code, 401)
        self.assertEqual(chave_invalida.status_code, 401)
        self.assertEqual(sem_chave['WWW-Authenticate'], 'Bearer')

    def test_crud_completo_com_imagens_em_json(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=diretorio):
            criado = self.criar_projeto()
            projeto_id = criado['id']
            self.assertTrue(criado['capa_url'].endswith('.webp'))
            self.assertEqual(len(criado['imagens']), 1)
            self.assertEqual(criado['data_desenvolvimento'], '2026-08-01')
            self.assertTrue(criado['destaque'])

            listagem = self.client.get(
                reverse('colecao_projetos_api'),
                **self.autorizacao,
            )
            self.assertEqual(listagem.json()['total'], 1)

            atualizacao = self.requisicao_json(
                'patch',
                reverse('detalhe_projeto_api', args=[projeto_id]),
                {'titulo': 'Projeto atualizado', 'url': ''},
            )
            self.assertEqual(atualizacao.status_code, 200)
            self.assertEqual(
                atualizacao.json()['projeto']['titulo'],
                'Projeto atualizado',
            )
            self.assertEqual(atualizacao.json()['projeto']['url'], '')

            exclusao = self.client.delete(
                reverse('detalhe_projeto_api', args=[projeto_id]),
                **self.autorizacao,
            )
            self.assertEqual(exclusao.status_code, 204)
            self.assertFalse(Projeto.objects.filter(pk=projeto_id).exists())

    def test_gerencia_ordem_dos_projetos_e_galeria(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=diretorio):
            primeiro = self.criar_projeto('Primeiro')
            segundo = self.criar_projeto('Segundo')

            organizacao = self.requisicao_json(
                'patch',
                reverse('organizacao_projetos_api'),
                {
                    'ordem': [segundo['id'], primeiro['id']],
                    'destaque': segundo['id'],
                },
            )
            self.assertEqual(organizacao.status_code, 200)
            self.assertEqual(
                list(Projeto.objects.values_list('pk', flat=True)),
                [segundo['id'], primeiro['id']],
            )

            adicao = self.requisicao_json(
                'post',
                reverse('colecao_imagens_api', args=[primeiro['id']]),
                {'imagens': [self.imagem_base64('segunda.png', 'yellow')]},
            )
            self.assertEqual(adicao.status_code, 201, adicao.content)
            imagens = list(
                Projeto.objects.get(pk=primeiro['id']).imagens.values_list(
                    'pk',
                    flat=True,
                )
            )
            ordem_imagens = self.requisicao_json(
                'patch',
                reverse('organizacao_imagens_api', args=[primeiro['id']]),
                {'ordem': list(reversed(imagens))},
            )
            self.assertEqual(ordem_imagens.status_code, 200)

            exclusao = self.client.delete(
                reverse(
                    'detalhe_imagem_api',
                    args=[primeiro['id'], imagens[0]],
                ),
                **self.autorizacao,
            )
            self.assertEqual(exclusao.status_code, 204)

    def test_recusa_dados_invalidos_sem_criar_projeto(self):
        resposta = self.requisicao_json('post', reverse('colecao_projetos_api'), {
            'titulo': '',
            'descricao': 'Descrição',
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertIn('titulo', resposta.json()['erro']['campos'])
        self.assertFalse(Projeto.objects.exists())

    def test_chave_rotacionada_perde_acesso_imediatamente(self):
        autorizacao_antiga = self.autorizacao
        usuario = get_user_model().objects.get(username='staff-api')
        _, chave_nova = ChaveAPI.rotacionar(usuario)

        resposta_antiga = self.client.get(
            reverse('colecao_projetos_api'),
            **autorizacao_antiga,
        )
        resposta_nova = self.client.get(
            reverse('colecao_projetos_api'),
            HTTP_AUTHORIZATION=f'Bearer {chave_nova}',
        )
        self.assertEqual(resposta_antiga.status_code, 401)
        self.assertEqual(resposta_nova.status_code, 200)


class MCPProjetosTest(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username='staff-mcp',
            is_staff=True,
        )
        _, chave = ChaveAPI.rotacionar(usuario)
        self.autorizacao = {'HTTP_AUTHORIZATION': f'Bearer {chave}'}

    def enviar(self, identificador, metodo, parametros=None):
        return self.client.post(
            reverse('endpoint_mcp'),
            data=json.dumps({
                'jsonrpc': '2.0',
                'id': identificador,
                'method': metodo,
                'params': parametros or {},
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json, text/event-stream',
            **self.autorizacao,
        )

    def test_handshake_e_lista_ferramentas(self):
        inicializacao = self.enviar(1, 'initialize', {
            'protocolVersion': '2025-06-18',
            'capabilities': {},
            'clientInfo': {'name': 'teste', 'version': '1.0'},
        })
        ferramentas = self.enviar(2, 'tools/list')

        self.assertEqual(inicializacao.status_code, 200)
        self.assertEqual(
            inicializacao.json()['result']['serverInfo']['name'],
            'portfolio-projetos',
        )
        nomes = {
            item['name']
            for item in ferramentas.json()['result']['tools']
        }
        self.assertEqual(len(nomes), 9)
        self.assertIn('criar_projeto', nomes)
        self.assertIn('organizar_imagens_projeto', nomes)

    def test_ferramenta_cria_e_lista_projeto(self):
        criacao = self.enviar(1, 'tools/call', {
            'name': 'criar_projeto',
            'arguments': {
                'titulo': 'Projeto via MCP',
                'descricao': 'Criado pelo protocolo.',
            },
        })
        listagem = self.enviar(2, 'tools/call', {
            'name': 'listar_projetos',
            'arguments': {},
        })

        self.assertFalse(criacao.json()['result']['isError'])
        self.assertEqual(
            criacao.json()['result']['structuredContent']['projeto']['titulo'],
            'Projeto via MCP',
        )
        self.assertEqual(
            listagem.json()['result']['structuredContent']['total'],
            1,
        )

    def test_notificacao_retorna_accepted(self):
        resposta = self.client.post(
            reverse('endpoint_mcp'),
            data=json.dumps({
                'jsonrpc': '2.0',
                'method': 'notifications/initialized',
            }),
            content_type='application/json',
            **self.autorizacao,
        )
        self.assertEqual(resposta.status_code, 202)


@override_settings(DEBUG=False)
class PaginasErroTest(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff-erros',
            password='senha-segura',
            is_staff=True,
        )
        self.usuario_comum = get_user_model().objects.create_user(
            username='comum-erros',
            password='senha-segura',
        )

    def test_handlers_globais_estao_registrados(self):
        resolvedor = get_resolver()

        self.assertEqual(
            resolvedor.resolve_error_handler(400).__module__,
            'app.error_views',
        )
        self.assertEqual(
            resolvedor.resolve_error_handler(403).__module__,
            'app.error_views',
        )
        self.assertEqual(
            resolvedor.resolve_error_handler(404).__module__,
            'app.error_views',
        )
        self.assertEqual(
            resolvedor.resolve_error_handler(500).__module__,
            'app.error_views',
        )

    def test_exibe_pagina_404_personalizada(self):
        resposta = self.client.get('/pagina-que-nao-existe/')

        self.assertEqual(resposta.status_code, 404)
        self.assertTemplateUsed(resposta, 'erro.html')
        self.assertContains(
            resposta,
            'Página não encontrada',
            status_code=404,
        )
        self.assertContains(resposta, '404', status_code=404)

    def test_exibe_pagina_403_personalizada(self):
        self.client.force_login(self.usuario_comum)
        resposta = self.client.get(reverse('painel_chave_api'))

        self.assertEqual(resposta.status_code, 403)
        self.assertTemplateUsed(resposta, 'erro.html')
        self.assertContains(resposta, 'Acesso negado', status_code=403)

    def test_exibe_pagina_405_personalizada(self):
        self.client.force_login(self.staff)
        resposta = self.client.put(reverse('painel_chave_api'))

        self.assertEqual(resposta.status_code, 405)
        self.assertTemplateUsed(resposta, 'erro.html')
        self.assertContains(resposta, 'Ação não permitida', status_code=405)
        self.assertContains(resposta, 'GET, POST', status_code=405)
        self.assertEqual(resposta['Allow'], 'GET, POST')

    def test_exibe_pagina_403_para_falha_csrf(self):
        cliente_csrf = Client(enforce_csrf_checks=True)
        cliente_csrf.force_login(self.staff)
        resposta = cliente_csrf.post(reverse('painel_chave_api'))

        self.assertEqual(resposta.status_code, 403)
        self.assertTemplateUsed(resposta, 'erro.html')
        self.assertContains(resposta, 'sessão do formulário expirou', status_code=403)

    def test_exibe_pagina_500_sem_detalhes_tecnicos(self):
        resposta = erro_500(RequestFactory().get('/falha/'))

        self.assertEqual(resposta.status_code, 500)
        self.assertContains(resposta, 'Erro interno', status_code=500)
        self.assertNotContains(
            resposta,
            'Traceback',
            status_code=500,
        )

    def test_erro_de_api_continua_sendo_json(self):
        resposta = self.client.get('/api/v1/recurso-inexistente/')

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta['Content-Type'], 'application/json')
        self.assertEqual(resposta.json()['erro']['codigo'], 'erro_404')

    def test_metodo_invalido_da_api_retorna_json_e_allow(self):
        _, chave = ChaveAPI.rotacionar(self.staff)
        resposta = self.client.put(
            reverse('colecao_projetos_api'),
            data='{}',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {chave}',
        )

        self.assertEqual(resposta.status_code, 405)
        self.assertEqual(resposta['Content-Type'], 'application/json')
        self.assertEqual(resposta['Allow'], 'GET, POST')
        self.assertEqual(resposta.json()['erro']['codigo'], 'erro_405')


class ConfiguracaoDeployTest(SimpleTestCase):
    def test_build_da_vercel_aplica_migrations(self):
        configuracao = json.loads(
            (settings.BASE_DIR / 'vercel.json').read_text(encoding='utf-8')
        )

        self.assertEqual(
            configuracao['buildCommand'],
            'python manage.py migrate --noinput',
        )
