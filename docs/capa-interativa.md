# Base da cover, preloader e inclinação

A `main` parte do commit `a6abfb1` — “feat (icons): adiciona e altera os icons”.
O layout desktop, os assets e as animações originais da página foram
preservados. A capa recebeu o preloader, a inclinação e os ajustes mobile
de centralização e espaçamento descritos abaixo.

## Preloader

Vídeo WebM automático, mínimo de dois segundos e saída deslizando para cima
depois que a página, as fontes e a reprodução terminam. É
dispensado em cache HTTP e retornos pelo histórico. Uma navegação nova ou um
recarregamento fora do cache exibe o preloader, mesmo após outras visitas.

- `static/js/preloader.js`: controle de carregamento, tempo e cache.
- `static/css/preloader.css`: estilos exclusivos da camada de carregamento.
- `static/videos/hv-preloader.webm`: mesmo vídeo já aprovado.
- `scripts/preparar-video-capa.py`: converte o vídeo original sem sobrepor a logo estática.
- `scripts/tests/preloader.test.cjs`: testes de tempo, cache e recuperação.

As configurações ficam em `CONFIG_PRELOADER`, no início de `preloader.js`.
O vídeo toca uma vez e conserva o último frame até a saída. Não há imagem
substituta no HTML nem transição para PNG/WebP dentro do vídeo convertido.
Se o vídeo falhar, a barra continua e a página é liberada normalmente.

A barra e o contador ficam centralizados na parte inferior. A porcentagem
representa o avanço das etapas (reprodução, tempo mínimo, página e fontes),
não bytes transferidos. Ela não retrocede e só chega a 100% quando tudo está
pronto. `pausaConclusao` mantém 100% visível por 180 ms antes do slide.
O limite de espera continua em 15 segundos para evitar bloqueio por falhas.

Para testar durante o desenvolvimento, use Ctrl + Shift + R para recarregar
fora do cache. A antiga marca `hv:preloader:v1` do sessionStorage é ignorada:
uma visita anterior não é prova de que a página atual veio do cache. Os links
do script e do CSS incluem uma versão para atualizar os arquivos no navegador.

## Inclinação com mouse

`static/js/cover.js` inclina a logo e Henrique Vieira ao passar o mouse na
apresentação. O texto superior, a descrição e DEV / 01 ficam fixos. O card
fixado responde de forma independente. Não há interação nova no fundo.

A camada externa da logo mantém suas coordenadas originais em CSS. O GSAP
movimenta somente a camada interna, preservando o posicionamento ao iniciar,
ao sair com o mouse e ao mudar de breakpoint. O card também tem uma camada
externa de medida original e uma figura interna para a inclinação.

As interações respeitam movimento reduzido. No desktop, continuam usando o
mouse com ponteiro fino. O `main.css` original não recebeu alterações.

## Inclinação por orientação no celular

Em aparelhos com ponteiro de toque, contexto seguro (HTTPS) e suporte a
`DeviceOrientationEvent`, a capa oferece o botão **Ativar inclinação**.
O efeito sempre começa por uma escolha do visitante. Quando existe
`requestPermission()`, a solicitação ocorre diretamente nesse toque.
Não há pedido de acesso ao magnetômetro ou à localização.

A primeira leitura válida calibra a posição neutra de como o aparelho está
sendo segurado. A logo e o nome inclinam até 10 graus; o card, até 14 graus.
O movimento atinge a amplitude máxima com 18 graus de giro do aparelho,
com deslocamentos de até 8 px na apresentação e 6 px no card, suavizados
pelo GSAP. Os textos de apoio e o
fundo continuam fixos. A leitura compensa a orientação da tela e recalibra
ao girá-la, voltar à capa ou retornar à aba.

O botão também permite desativar. A leitura é suspensa fora da capa, durante
o preloader ou com a aba oculta. Negar a permissão, receber dados nulos ou
ficar cinco segundos sem uma leitura válida mantém a composição estática.
Sem suporte ou com preferência por movimento reduzido, o controle fica oculto.

- `scripts/tests/cover.test.cjs`: orientação, permissões, pausa e mouse.
- [API Device Orientation, W3C](https://www.w3.org/TR/orientation-event/).

No mobile, o texto superior, as duas linhas do nome, a logo e a descrição
ficam centralizados. As margens entre as linhas do nome são simétricas e
a descrição usa quebra de linhas equilibrada. O controle ocupa uma linha
após o card, com 16 px de espaço acima e 24 px abaixo, além de 14 px de
padding vertical dentro do botão.

## Pendente: mobile

- [x] Centralizar a apresentação e dar mais respiro ao botão no celular.
- [x] Implementar inclinação por orientação, com ativação por toque e fallback estático.
- [ ] Validar sensibilidade e permissão em iPhone/Safari e Android/Chrome reais.

A inclinação pode ser testada no site publicado por HTTPS; acessar o servidor local pelo
IP do computador em HTTP normalmente não disponibiliza os sensores.

## Verificação

O deploy declara o framework `django` e a entrada `setup/wsgi.py` em
`vercel.json`. Assim, a Vercel executa as migrações no ambiente Python do
projeto e atende as rotas pelo WSGI, sem reescrevê-las para `/api/index`.
Isso evita executar as migrações com o Python do sistema e um driver
PostgreSQL instalado para outra versão de Python.

```sh
node --test scripts/tests/preloader.test.cjs
node --test scripts/tests/cover.test.cjs
python manage.py test --noinput
```
