# Base da cover, preloader e inclinação

A `main` parte do commit `a6abfb1` — “feat (icons): adiciona e altera os icons”.
O layout, as regras responsivas, os assets e as animações originais da página
foram preservados. Os complementos são somente o preloader e a inclinação.

## Preloader

Mantido como na versão aprovada: vídeo WebM automático, mínimo de dois segundos
e saída deslizando para cima depois que a página e as fontes carregam. É
dispensado em cache HTTP, retornos pelo histórico e revisitas da mesma sessão.

- `static/js/preloader.js`: controle de carregamento, tempo e cache.
- `static/css/preloader.css`: estilos exclusivos da camada de carregamento.
- `static/videos/hv-preloader.webm`: mesmo vídeo já aprovado.
- `scripts/tests/preloader.test.cjs`: testes de tempo, cache e recuperação.

As configurações ficam em `CONFIG_PRELOADER`, no início de `preloader.js`.
Para repetir uma primeira visita durante o desenvolvimento, use uma sessão
anônima nova ou remova `hv:preloader:v1` do sessionStorage.

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

```sh
node --test scripts/tests/preloader.test.cjs
python manage.py test --noinput
```
