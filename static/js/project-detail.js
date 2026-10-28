function iniciarAcessoRapidoProjeto(janela = window) {
  const documento = janela.document;
  const acesso = documento.querySelector('[data-project-primary-access]');
  const barra = documento.querySelector('[data-project-launchbar]');
  if (!acesso || !barra || !janela.IntersectionObserver) return;

  let acessoVisivel = true;
  let encerrado = false;
  const atualizar = () => {
    if (encerrado) return;
    // Não retire da tela um link que ainda está sendo usado pelo teclado.
    if (!documento.hidden && !barra.hidden && barra.contains(documento.activeElement)) return;
    barra.hidden = acessoVisivel || documento.hidden;
  };
  const depoisDoFoco = () => janela.queueMicrotask(atualizar);
  const observador = new janela.IntersectionObserver(([entrada]) => {
    acessoVisivel = entrada.isIntersecting && entrada.intersectionRatio >= 1;
    atualizar();
  }, { rootMargin: '-80px 0px 0px 0px', threshold: 1 });
  observador.observe(acesso);
  documento.addEventListener('visibilitychange', atualizar);
  barra.addEventListener('focusout', depoisDoFoco);
  return () => {
    encerrado = true;
    observador.disconnect();
    documento.removeEventListener('visibilitychange', atualizar);
    barra.removeEventListener('focusout', depoisDoFoco);
    barra.hidden = true;
  };
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => iniciarAcessoRapidoProjeto());
}
