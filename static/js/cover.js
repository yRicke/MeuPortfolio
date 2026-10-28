const CONFIG_CAPA = Object.freeze({
  inclinacaoLogo: 7,
  inclinacaoProjeto: 9,
});

function iniciarCapa() {
  const capa = document.querySelector('.cover-section');
  if (!capa || !window.gsap) return;

  const media = gsap.matchMedia();
  media.add({
    desktop: '(min-width: 769px)',
    ponteiro: '(hover: hover) and (pointer: fine)',
    reduzir: '(prefers-reduced-motion: reduce)',
  }, (contexto) => {
    if (!contexto.conditions.desktop || !contexto.conditions.ponteiro
        || contexto.conditions.reduzir) return;

    const eventos = new AbortController();
    const restauradores = [];
    const preparar = (elemento, superficie, inclinacao, deslocamento) => {
      const animar = Object.fromEntries(['x', 'y', 'rotationX', 'rotationY'].map(
        (propriedade) => [propriedade, gsap.quickTo(elemento, propriedade, {
          duration: 0.65, ease: 'power3.out',
        })],
      ));
      const restaurar = () => Object.values(animar).forEach((mover) => mover(0));
      restauradores.push(restaurar);
      superficie.addEventListener('pointermove', (evento) => {
        if (document.documentElement.classList.contains('is-preloading')
            || evento.pointerType === 'touch') return;
        const caixa = superficie.getBoundingClientRect();
        const x = gsap.utils.clamp(-1, 1, (evento.clientX - caixa.left) / caixa.width * 2 - 1);
        const y = gsap.utils.clamp(-1, 1, (evento.clientY - caixa.top) / caixa.height * 2 - 1);
        animar.x(x * deslocamento);
        animar.y(y * deslocamento);
        animar.rotationX(-y * inclinacao);
        animar.rotationY(x * inclinacao);
      }, { passive: true, signal: eventos.signal });
      superficie.addEventListener('pointerleave', restaurar, { signal: eventos.signal });
      superficie.addEventListener('focusin', restaurar, { signal: eventos.signal });
    };

    capa.classList.add('cover-has-tilt');
    const apresentacao = capa.querySelector('[data-cover-position]');
    preparar(capa.querySelector('[data-cover-logo-tilt]'), apresentacao, CONFIG_CAPA.inclinacaoLogo, 12);
    preparar(capa.querySelector('[data-cover-title]'), apresentacao, CONFIG_CAPA.inclinacaoLogo, 12);
    preparar(capa.querySelector('[data-cover-project-tilt]'), capa.querySelector('[data-cover-art]'), CONFIG_CAPA.inclinacaoProjeto, 9);
    capa.addEventListener('pointerleave', () => {
      restauradores.forEach((restaurar) => restaurar());
    }, { signal: eventos.signal });

    return () => {
      eventos.abort();
      capa.classList.remove('cover-has-tilt');
    };
  });
  window.addEventListener('pagehide', (evento) => {
    if (!evento.persisted) media.revert();
  }, { once: true });
}
