# Base da cover, preloader e inclinação

A `main` parte do commit `a6abfb1` — “feat (icons): adiciona e altera os icons”.
O layout, as regras responsivas, os assets e as animações originais da página
foram preservados. Os complementos são somente o preloader e a inclinação.

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

As interações respeitam movimento reduzido e funcionam apenas em desktop
com ponteiro fino. O `main.css` original não recebeu alterações.

## Pendente: mobile

- [ ] Pensar na centralização e no equilíbrio da composição no celular.
- [ ] Avaliar a inclinação por orientação do aparelho, com permissão explícita,
  fallback estático e validação em iPhone e Android reais.

Esses ajustes ficam para uma próxima solicitação. Por enquanto, o mobile
mantém o layout de `a6abfb1`.

## Verificação

O deploy declara o framework `django` e a entrada `setup/wsgi.py` em
`vercel.json`. Assim, a Vercel executa as migrações no ambiente Python do
projeto e atende as rotas pelo WSGI, sem reescrevê-las para `/api/index`.
Isso evita executar as migrações com o Python do sistema e um driver
PostgreSQL instalado para outra versão de Python.

```sh
node --test scripts/tests/preloader.test.cjs
python manage.py test --noinput
```
