const CONFIG_PRELOADER = Object.freeze({
  duracaoMinima: 2000,
  pausaConclusao: 180,
  duracaoSaida: 750,
  limiteCarregamento: 15000,
  velocidadeVideo: 4,
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
  return !janela.matchMedia('(prefers-reduced-motion: reduce)').matches
    && !navegacaoEmCache(janela);
}

function iniciarPreloader(janela) {
  const documento = janela.document;
  const raiz = documento.documentElement;
  if (!deveMostrarPreloader(janela)) {
    return { montar: () => documento.querySelector('[data-page-preloader]')?.remove() };
  }

  raiz.classList.add('is-preloading');
  let fase = 'carregando';
  let inicio = null;
  let camada;
  let video;
  let videoConcluido = false;
  let indicador;
  let barra;
  let porcentagem;
  let progressoAtual = -1;
  let paginaPronta = documento.readyState === 'complete';
  let fontesProntas = !documento.fonts || documento.fonts.status === 'loaded';
  let esperaMinima;
  let esperaProgresso;
  let esperaConclusao;
  let esperaTransicao;
  const superficies = [];

  const atualizarProgresso = (concluido = false) => {
    const tempo = Math.min(1, (janela.performance.now() - inicio) / CONFIG_PRELOADER.duracaoMinima);
    const reproducao = videoConcluido ? 1 : (
      Number.isFinite(video?.duration) && video.duration > 0
        ? Math.min(1, video.currentTime / video.duration) : 0
    );
    // Progresso das etapas, sem estimar bytes de uma página de tamanho desconhecido.
    const estimativa = Math.floor(tempo * 20 + reproducao * 70
      + (paginaPronta ? 5 : 0) + (fontesProntas ? 5 : 0));
    const valor = concluido ? 100 : Math.max(progressoAtual, Math.min(99, estimativa));
    if (valor === progressoAtual) return;
    progressoAtual = valor;
    indicador?.setAttribute('aria-valuenow', String(valor));
    if (porcentagem) porcentagem.textContent = `${valor}%`;
    if (barra) barra.style.transform = `scaleX(${valor / 100})`;
  };

  const acompanharProgresso = () => {
    if (fase !== 'carregando') return;
    atualizarProgresso();
    esperaProgresso = janela.setTimeout(acompanharProgresso, 50);
  };

  const finalizar = () => {
    if (fase === 'concluido') return;
    fase = 'concluido';
    janela.clearTimeout(limite);
    janela.clearTimeout(esperaMinima);
    janela.clearTimeout(esperaProgresso);
    janela.clearTimeout(esperaConclusao);
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
    janela.dispatchEvent(new janela.Event('preloader:complete'));
  };

  const deslizar = () => {
    if (fase !== 'pronto') return;
    fase = 'saindo';
    camada.addEventListener('transitionend', (evento) => {
      if (evento.target === camada && evento.propertyName === 'transform') finalizar();
    });
    camada.classList.add('is-leaving');
    esperaTransicao = janela.setTimeout(finalizar, CONFIG_PRELOADER.duracaoSaida + 100);
  };

  const sair = () => {
    if (fase !== 'carregando') return;
    if (!camada || janela.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      finalizar();
      return;
    }
    fase = 'pronto';
    janela.clearTimeout(limite);
    janela.clearTimeout(esperaProgresso);
    atualizarProgresso(true);
    esperaConclusao = janela.setTimeout(deslizar, CONFIG_PRELOADER.pausaConclusao);
  };

  const programarSaida = () => {
    if (fase !== 'carregando' || inicio === null
        || !paginaPronta || !fontesProntas || !videoConcluido) return;
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
    indicador = camada.querySelector('[data-preloader-progress]');
    barra = camada.querySelector('[data-preloader-progress-fill]');
    porcentagem = camada.querySelector('[data-preloader-percentage]');
    video = camada.querySelector('[data-preloader-video]');
    videoConcluido = !video;
    if (video) {
      const concluirVideo = () => {
        if (fase !== 'carregando') return;
        videoConcluido = true;
        programarSaida();
      };
      // Sem loop nem troca de imagem: o navegador conserva o último frame no ended.
      video.addEventListener('ended', concluirVideo, { once: true });
      video.addEventListener('error', concluirVideo, { once: true });
      video.muted = true;
      video.loop = false;
      video.defaultPlaybackRate = CONFIG_PRELOADER.velocidadeVideo;
      video.playbackRate = CONFIG_PRELOADER.velocidadeVideo;
      video.src = video.dataset.src;
      try {
        video.load();
        video.play()?.catch(concluirVideo);
      } catch {
        concluirVideo();
      }
    }
    acompanharProgresso();
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
    videoConcluido = true;
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
