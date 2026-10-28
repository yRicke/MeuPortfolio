const CONFIG_CAPA = Object.freeze({
  inclinacaoLogo: 7,
  inclinacaoProjeto: 9,
  amplitudeSensor: 22,
  zonaMortaSensor: 0.4,
  limiteSensor: 5000,
});

function calcularInclinacaoSensor(evento, referencia, anguloTela = 0) {
  if (!Number.isFinite(evento.beta) || !Number.isFinite(evento.gamma)) return null;
  const diferenca = (valor, origem) => ((valor - origem + 540) % 360) - 180;
  const beta = diferenca(evento.beta, referencia.beta);
  const gamma = diferenca(evento.gamma, referencia.gamma);
  const angulo = anguloTela * Math.PI / 180;
  const normalizar = (valor) => Math.sign(valor) * Math.min(1,
    Math.max(0, Math.abs(valor) - CONFIG_CAPA.zonaMortaSensor)
      / (CONFIG_CAPA.amplitudeSensor - CONFIG_CAPA.zonaMortaSensor));
  return {
    x: normalizar(gamma * Math.cos(angulo) + beta * Math.sin(angulo)),
    y: normalizar(beta * Math.cos(angulo) - gamma * Math.sin(angulo)),
  };
}

function criarInclinacaoCapa(elemento, inclinacao, deslocamento) {
  if (!elemento) return null;
  const animar = Object.fromEntries(['x', 'y', 'rotationX', 'rotationY'].map(
    (propriedade) => [propriedade, gsap.quickTo(elemento, propriedade, {
      duration: 0.65, ease: 'power3.out',
    })],
  ));
  return {
    mover: (x, y) => {
      animar.x(x * deslocamento);
      animar.y(y * deslocamento);
      animar.rotationX(-y * inclinacao);
      animar.rotationY(x * inclinacao);
    },
    restaurar: () => Object.values(animar).forEach((mover) => mover(0)),
  };
}

function iniciarInclinacaoMobile(capa) {
  const controle = capa.querySelector('[data-cover-motion]');
  const botao = controle?.querySelector('button');
  if (!botao || !window.isSecureContext || !window.DeviceOrientationEvent) return;
  const rotulo = controle.querySelector('[data-cover-motion-label]');
  const status = controle.querySelector('[data-cover-motion-status]');
  const eventos = new AbortController();
  const camadas = [
    criarInclinacaoCapa(capa.querySelector('[data-cover-logo-tilt]'), 5, 4),
    criarInclinacaoCapa(capa.querySelector('[data-cover-title]'), 5, 4),
    criarInclinacaoCapa(capa.querySelector('[data-cover-project-tilt]'), 7, 3),
  ].filter(Boolean);
  let ativo = false;
  let descartado = false;
  let naTela = !window.IntersectionObserver;
  let paginaAtiva = true;
  let ouvindo = false;
  let referencia = null;
  let leitura = null;
  let quadro = null;
  let esperaSensor;

  controle.hidden = false;
  botao.disabled = false;
  const atualizarControle = (mensagem = '') => {
    botao.setAttribute('aria-pressed', String(ativo));
    rotulo.textContent = ativo ? 'Desativar inclinação' : 'Ativar inclinação';
    status.textContent = mensagem;
  };
  atualizarControle();

  const recentralizar = () => {
    referencia = null;
    leitura = null;
    if (quadro !== null) window.cancelAnimationFrame(quadro);
    quadro = null;
    camadas.forEach((camada) => camada.restaurar());
  };
  const pararLeitura = () => {
    window.removeEventListener('deviceorientation', receberOrientacao);
    ouvindo = false;
    window.clearTimeout(esperaSensor);
    recentralizar();
  };
  const desativar = (mensagem = '') => {
    ativo = false;
    capa.classList.remove('cover-has-tilt');
    pararLeitura();
    atualizarControle(mensagem);
  };
  const renderizar = () => {
    quadro = null;
    const angulo = window.screen.orientation?.angle ?? window.orientation ?? 0;
    const inclinacao = calcularInclinacaoSensor(leitura, referencia, angulo);
    camadas.forEach((camada) => camada.mover(inclinacao.x, inclinacao.y));
  };
  function receberOrientacao(evento) {
    if (!ouvindo || !Number.isFinite(evento.beta) || !Number.isFinite(evento.gamma)) return;
    window.clearTimeout(esperaSensor);
    leitura = { beta: evento.beta, gamma: evento.gamma };
    referencia ??= leitura;
    if (quadro === null) quadro = window.requestAnimationFrame(renderizar);
  }
  const sincronizarLeitura = () => {
    const podeLer = ativo && naTela && paginaAtiva && !document.hidden
      && !document.documentElement.classList.contains('is-preloading');
    if (!podeLer) {
      if (ouvindo) pararLeitura();
      return;
    }
    if (ouvindo) return;
    ouvindo = true;
    window.addEventListener('deviceorientation', receberOrientacao, { passive: true });
    esperaSensor = window.setTimeout(() => {
      desativar('Movimento indisponível neste aparelho ou navegador.');
    }, CONFIG_CAPA.limiteSensor);
  };

  botao.addEventListener('click', async () => {
    if (ativo) {
      desativar();
      return;
    }
    if (botao.disabled) return;
    botao.disabled = true;
    status.textContent = '';
    try {
      // Deve acontecer diretamente no clique para manter a ativação exigida no iOS.
      const Sensor = window.DeviceOrientationEvent;
      if (typeof Sensor.requestPermission === 'function'
          && await Sensor.requestPermission() !== 'granted') {
        if (!descartado) atualizarControle('Permissão de movimento não concedida.');
        return;
      }
      if (descartado) return;
      ativo = true;
      capa.classList.add('cover-has-tilt');
      atualizarControle();
      sincronizarLeitura();
    } catch {
      if (!descartado) desativar('Não foi possível ativar o movimento neste navegador.');
    } finally {
      if (!descartado) botao.disabled = false;
    }
  }, { signal: eventos.signal });

  const observador = window.IntersectionObserver ? new window.IntersectionObserver(([entrada]) => {
    naTela = entrada.isIntersecting;
    sincronizarLeitura();
  }) : null;
  observador?.observe(capa);
  document.addEventListener('visibilitychange', sincronizarLeitura, { signal: eventos.signal });
  window.addEventListener('preloader:complete', sincronizarLeitura, { signal: eventos.signal });
  window.addEventListener('pagehide', () => {
    paginaAtiva = false;
    sincronizarLeitura();
  }, { signal: eventos.signal });
  window.addEventListener('pageshow', () => {
    paginaAtiva = true;
    sincronizarLeitura();
  }, { signal: eventos.signal });
  if (window.screen.orientation?.addEventListener) {
    window.screen.orientation.addEventListener('change', recentralizar, { signal: eventos.signal });
  } else {
    window.addEventListener('orientationchange', recentralizar, { signal: eventos.signal });
  }

  return () => {
    descartado = true;
    ativo = false;
    eventos.abort();
    observador?.disconnect();
    window.removeEventListener('deviceorientation', receberOrientacao);
    window.clearTimeout(esperaSensor);
    if (quadro !== null) window.cancelAnimationFrame(quadro);
    capa.classList.remove('cover-has-tilt');
    controle.hidden = true;
    atualizarControle();
  };
}

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
      const movimento = criarInclinacaoCapa(elemento, inclinacao, deslocamento);
      if (!movimento || !superficie) return;
      const { restaurar } = movimento;
      restauradores.push(restaurar);
      superficie.addEventListener('pointermove', (evento) => {
        if (document.documentElement.classList.contains('is-preloading')
            || evento.pointerType === 'touch') return;
        const caixa = superficie.getBoundingClientRect();
        const x = gsap.utils.clamp(-1, 1, (evento.clientX - caixa.left) / caixa.width * 2 - 1);
        const y = gsap.utils.clamp(-1, 1, (evento.clientY - caixa.top) / caixa.height * 2 - 1);
        movimento.mover(x, y);
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
  media.add({
    toque: '(hover: none) and (pointer: coarse)',
    reduzir: '(prefers-reduced-motion: reduce)',
  }, (contexto) => {
    if (!contexto.conditions.toque || contexto.conditions.reduzir) return;
    return iniciarInclinacaoMobile(capa);
  });
  window.addEventListener('pagehide', (evento) => {
    if (!evento.persisted) media.revert();
  });
}
