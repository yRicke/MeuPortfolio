const CONFIG_PRELOADER = Object.freeze({
  duracaoMinima: 2000,
  duracaoSaida: 750,
  limiteCarregamento: 15000,
  velocidadeVideo: 4,
  chaveSessao: 'hv:preloader:v1',
});

function navegacaoEmCache(janela) {
  const navegacao = janela.performance?.getEntriesByType?.('navigation')[0];
  if (!navegacao) return false;
  return navegacao.type === 'back_forward'
    || navegacao.deliveryType === 'cache'
    || (navegacao.responseEnd > 0 && navegacao.transferSize === 0 && navegacao.decodedBodySize > 0)
    || (navegacao.responseEnd > 0 && navegacao.transferSize > 0
      && navegacao.transferSize < navegacao.encodedBodySize);
}

function deveMostrarPreloader(janela) {
  if (janela.matchMedia('(prefers-reduced-motion: reduce)').matches
      || navegacaoEmCache(janela)) return false;
  try {
    return janela.sessionStorage.getItem(CONFIG_PRELOADER.chaveSessao) !== '1';
  } catch {
    return true;
  }
}

function iniciarPreloader(janela) {
  const documento = janela.document;
  const raiz = documento.documentElement;
  if (!deveMostrarPreloader(janela)) {
    try {
      janela.sessionStorage.setItem(CONFIG_PRELOADER.chaveSessao, '1');
    } catch { /* O preloader também pode ser dispensado sem storage. */ }
    return { montar: () => documento.querySelector('[data-page-preloader]')?.remove() };
  }

  raiz.classList.add('is-preloading');
  let fase = 'carregando';
  let inicio = null;
  let camada;
  let video;
  let paginaPronta = documento.readyState === 'complete';
  let fontesProntas = !documento.fonts || documento.fonts.status === 'loaded';
  let esperaMinima;
  let esperaTransicao;
  const superficies = [];

  const lembrarVisita = () => {
    try {
      janela.sessionStorage.setItem(CONFIG_PRELOADER.chaveSessao, '1');
    } catch { /* Navegação em cache ainda funciona sem acesso ao storage. */ }
  };

  const finalizar = () => {
    if (fase === 'concluido') return;
    fase = 'concluido';
    janela.clearTimeout(limite);
    janela.clearTimeout(esperaMinima);
    janela.clearTimeout(esperaTransicao);
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
    camada?.remove();
    raiz.classList.remove('is-preloading');
    superficies.forEach(({ elemento, inerte, ocupado }) => {
      elemento.inert = inerte;
      if (ocupado === null) elemento.removeAttribute('aria-busy');
      else elemento.setAttribute('aria-busy', ocupado);
    });
    lembrarVisita();
    janela.dispatchEvent(new janela.Event('preloader:complete'));
  };

  const sair = () => {
    if (fase !== 'carregando') return;
    if (!camada || janela.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      finalizar();
      return;
    }
    fase = 'saindo';
    janela.clearTimeout(limite);
    camada.addEventListener('transitionend', (evento) => {
      if (evento.target === camada && evento.propertyName === 'transform') finalizar();
    });
    camada.classList.add('is-leaving');
    esperaTransicao = janela.setTimeout(finalizar, CONFIG_PRELOADER.duracaoSaida + 100);
  };

  const programarSaida = () => {
    if (fase !== 'carregando' || inicio === null || !paginaPronta || !fontesProntas) return;
    janela.clearTimeout(esperaMinima);
    const restante = CONFIG_PRELOADER.duracaoMinima - (janela.performance.now() - inicio);
    esperaMinima = janela.setTimeout(sair, Math.max(0, restante));
  };

  const montar = () => {
    if (inicio !== null || fase !== 'carregando') return;
    camada = documento.querySelector('[data-page-preloader]');
    if (!camada) return;
    inicio = janela.performance.now();
    camada.style.setProperty('--preloader-exit-duration', `${CONFIG_PRELOADER.duracaoSaida}ms`);
    video = camada.querySelector('[data-preloader-video]');
    if (video) {
      const mostrarMarca = () => {
        if (fase !== 'concluido') camada.classList.add('has-fallback');
      };
      video.addEventListener('error', mostrarMarca, { once: true });
      video.muted = true;
      video.loop = true;
      video.defaultPlaybackRate = CONFIG_PRELOADER.velocidadeVideo;
      video.playbackRate = CONFIG_PRELOADER.velocidadeVideo;
      video.src = video.dataset.src;
      try {
        video.load();
        video.play()?.catch(mostrarMarca);
      } catch {
        mostrarMarca();
      }
    }
    programarSaida();
  };

  const prepararDocumento = () => {
    montar();
    if (fase === 'concluido') return;
    documento.querySelectorAll('.site-main, [data-site-nav]').forEach((elemento) => {
      superficies.push({ elemento, inerte: elemento.inert, ocupado: elemento.getAttribute('aria-busy') });
      elemento.inert = true;
      elemento.setAttribute('aria-busy', 'true');
    });
  };

  const limite = janela.setTimeout(() => {
    paginaPronta = true;
    fontesProntas = true;
    montar();
    if (inicio === null) finalizar();
    else programarSaida();
  }, CONFIG_PRELOADER.limiteCarregamento);

  janela.addEventListener('load', () => {
    if (navegacaoEmCache(janela)) {
      finalizar();
      return;
    }
    paginaPronta = true;
    if (documento.fonts?.status === 'loading') {
      fontesProntas = false;
      documento.fonts.ready.then(() => {
        fontesProntas = true;
        programarSaida();
      });
    }
    programarSaida();
  }, { once: true });
  janela.addEventListener('pagehide', finalizar, { once: true });
  janela.addEventListener('pageshow', (evento) => {
    if (evento.persisted) finalizar();
  });
  if (!fontesProntas) {
    const fontesConcluidas = () => {
      fontesProntas = true;
      programarSaida();
    };
    documento.fonts.ready.then(fontesConcluidas, fontesConcluidas);
  }
  if (documento.readyState === 'loading') {
    documento.addEventListener('DOMContentLoaded', prepararDocumento, { once: true });
  } else {
    prepararDocumento();
  }
  return { montar };
}

if (typeof window !== 'undefined') {
  window.preloaderCapa = iniciarPreloader(window);
}
