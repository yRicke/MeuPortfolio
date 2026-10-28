const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const contexto = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../static/js/preloader.js'), 'utf8'), contexto);

class Elemento extends EventTarget {
  constructor() {
    super();
    this.classes = new Set();
    this.classList = {
      add: (...classes) => classes.forEach((nome) => this.classes.add(nome)),
      remove: (...classes) => classes.forEach((nome) => this.classes.delete(nome)),
      contains: (nome) => this.classes.has(nome),
    };
    this.style = { setProperty() {} };
    this.atributos = new Map();
    this.inert = false;
    this.removido = false;
  }
  getAttribute(nome) { return this.atributos.get(nome) ?? null; }
  setAttribute(nome, valor) { this.atributos.set(nome, valor); }
  removeAttribute(nome) { this.atributos.delete(nome); delete this[nome]; }
  remove() { this.removido = true; }
}

function ambiente(opcoes = {}) {
  let agora = 0;
  let proximoId = 0;
  const tarefas = new Map();
  const camada = new Elemento();
  const indicador = new Elemento();
  indicador.setAttribute('aria-valuenow', '0');
  const barra = new Elemento();
  const porcentagem = new Elemento();
  porcentagem.textContent = '0%';
  const video = new Elemento();
  video.dataset = { src: '/static/videos/hv-preloader.webm' };
  video.duration = opcoes.duracaoVideo ?? 8;
  video.currentTime = 0;
  video.reproducoes = 0;
  video.pausas = 0;
  let fimVideo;
  let inicioVideo;
  const terminarVideo = () => {
    janela.clearTimeout(fimVideo);
    video.currentTime = video.duration;
    video.ended = true;
    video.dispatchEvent(new Event('ended'));
  };
  video.load = () => {};
  video.pause = () => { video.pausas += 1; janela.clearTimeout(fimVideo); };
  video.play = () => {
    video.reproducoes += 1;
    if (opcoes.autoplayBloqueado) return Promise.reject(new Error('Autoplay bloqueado'));
    inicioVideo = agora;
    if (!opcoes.videoTravado && Number.isFinite(video.duration)) {
      fimVideo = janela.setTimeout(terminarVideo, video.duration / video.playbackRate * 1000);
    }
    return Promise.resolve();
  };
  camada.querySelector = (seletor) => ({
    '[data-preloader-video]': opcoes.semVideo ? null : video,
    '[data-preloader-progress]': indicador,
    '[data-preloader-progress-fill]': barra,
    '[data-preloader-percentage]': porcentagem,
  })[seletor];
  const principal = new Elemento();
  const nav = new Elemento();
  const documento = new EventTarget();
  documento.readyState = 'loading';
  documento.documentElement = new Elemento();
  documento.querySelector = () => camada.removido ? null : camada;
  documento.querySelectorAll = () => [principal, nav];
  let resolverFontes;
  documento.fonts = {
    status: opcoes.fontesCarregando ? 'loading' : 'loaded',
    ready: new Promise((resolve) => { resolverFontes = resolve; }),
  };
  const valores = new Map(opcoes.exibido ? [['hv:preloader:v1', '1']] : []);
  const janela = new EventTarget();
  janela.Event = Event;
  janela.document = documento;
  janela.performance = {
    now: () => agora,
    getEntriesByType: () => opcoes.navegacao ? [opcoes.navegacao] : [],
  };
  janela.matchMedia = () => ({ matches: !!opcoes.reduzir });
  janela.sessionStorage = {
    getItem: (nome) => {
      if (opcoes.storageBloqueado) throw new Error('Storage bloqueado');
      return valores.get(nome) ?? null;
    },
    setItem: (nome, valor) => {
      if (opcoes.storageBloqueado) throw new Error('Storage bloqueado');
      valores.set(nome, valor);
    },
  };
  janela.setTimeout = (acao, atraso) => {
    const id = ++proximoId;
    tarefas.set(id, { acao, tempo: agora + atraso });
    return id;
  };
  janela.clearTimeout = (id) => tarefas.delete(id);
  const moverRelogio = (tempo) => {
    agora = tempo;
    if (inicioVideo !== undefined && !opcoes.videoTravado && !video.ended && !video.pausas) {
      video.currentTime = Math.min(video.duration, (agora - inicioVideo) / 1000 * video.playbackRate);
    }
  };
  const avancar = (tempo) => {
    const destino = agora + tempo;
    while (true) {
      const proxima = [...tarefas.entries()].filter(([, t]) => t.tempo <= destino)
        .sort((a, b) => a[1].tempo - b[1].tempo)[0];
      if (!proxima) break;
      tarefas.delete(proxima[0]);
      moverRelogio(proxima[1].tempo);
      proxima[1].acao();
    }
    moverRelogio(destino);
  };
  const controle = contexto.iniciarPreloader(janela);
  controle.montar();
  documento.dispatchEvent(new Event('DOMContentLoaded'));
  return {
    janela, documento, camada, video, indicador, barra, porcentagem, principal, nav, valores, avancar,
    terminarVideo,
    carregar: () => janela.dispatchEvent(new Event('load')),
    fontesProntas: () => { documento.fonts.status = 'loaded'; resolverFontes(); },
    terminarSlide: () => {
      const evento = new Event('transitionend');
      Object.defineProperty(evento, 'propertyName', { value: 'transform' });
      camada.dispatchEvent(evento);
    },
  };
}

test('página rápida aguarda dois segundos antes do slide e libera a interação ao terminar', () => {
  const a = ambiente();
  let concluiu = 0;
  a.janela.addEventListener('preloader:complete', () => { concluiu += 1; });
  assert.equal(a.video.reproducoes, 1);
  assert.equal(a.video.playbackRate, 4);
  assert.equal(a.principal.inert, true);
  a.carregar();
  a.avancar(1999);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.avancar(1);
  assert.equal(a.porcentagem.textContent, '100%');
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.avancar(180);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
  assert.equal(a.camada.removido, false);
  a.terminarSlide();
  assert.equal(a.camada.removido, true);
  assert.equal(a.documento.documentElement.classList.contains('is-preloading'), false);
  assert.equal(a.principal.inert, false);
  assert.equal(a.nav.inert, false);
  assert.equal(a.principal.getAttribute('aria-busy'), null);
  assert.equal(a.video.pausas, 1);
  assert.equal(a.video.src, undefined);
  assert.equal(a.valores.get('hv:preloader:v1'), undefined);
  a.avancar(20000);
  assert.equal(concluiu, 1);
});

test('página lenta continua coberta depois do mínimo e só sai quando carregar', () => {
  const a = ambiente();
  a.avancar(4500);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.carregar();
  a.avancar(180);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

test('aguarda as fontes antes de abrir a página', async () => {
  const a = ambiente({ fontesCarregando: true });
  a.carregar();
  a.avancar(2100);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.fontesProntas();
  await Promise.resolve();
  a.avancar(180);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

for (const [nome, opcoes] of [
  ['cache HTTP informado pelo navegador', { navegacao: { deliveryType: 'cache' } }],
  ['cache HTTP sem transferência', { navegacao: { responseEnd: 100, transferSize: 0, decodedBodySize: 5000 } }],
  ['cache revalidado', { navegacao: { responseEnd: 100, transferSize: 300, encodedBodySize: 5000 } }],
  ['retorno pelo histórico', { navegacao: { type: 'back_forward' } }],
  ['movimento reduzido', { reduzir: true }],
]) {
  test(`não exibe nem carrega o vídeo em ${nome}`, () => {
    const a = ambiente(opcoes);
    assert.equal(a.documento.documentElement.classList.contains('is-preloading'), false);
    assert.equal(a.camada.removido, true);
    assert.equal(a.video.reproducoes, 0);
    assert.equal(a.video.src, undefined);
    assert.equal(a.principal.inert, false);
  });
}

for (const tipo of ['navigate', 'reload']) {
  test(`marca de sessão antiga não oculta uma navegação nova: ${tipo}`, () => {
    const a = ambiente({
      exibido: true,
      navegacao: {
        type: tipo, responseEnd: 100, transferSize: 5300,
        encodedBodySize: 5000, decodedBodySize: 8000,
      },
    });
    assert.equal(a.documento.documentElement.classList.contains('is-preloading'), true);
    assert.equal(a.video.reproducoes, 1);
    a.carregar();
    a.avancar(1999);
    assert.equal(a.camada.classList.contains('is-leaving'), false);
    a.avancar(1);
    a.avancar(180);
    assert.equal(a.camada.classList.contains('is-leaving'), true);
  });
}

test('recarregamento vindo do cache continua sem preloader mesmo com marca antiga', () => {
  const a = ambiente({ exibido: true, navegacao: { type: 'reload', deliveryType: 'cache' } });
  assert.equal(a.camada.removido, true);
  assert.equal(a.video.reproducoes, 0);
});

test('métricas ainda zeradas não são confundidas com cache', () => {
  const a = ambiente({ navegacao: { transferSize: 0, decodedBodySize: 0 } });
  assert.equal(a.documento.documentElement.classList.contains('is-preloading'), true);
});

test('uma resposta ainda baixando não é confundida com cache', () => {
  const a = ambiente({ navegacao: { responseEnd: 0, transferSize: 0, decodedBodySize: 5000 } });
  assert.equal(a.documento.documentElement.classList.contains('is-preloading'), true);
});

test('cache identificado ao completar as métricas dispensa imediatamente a camada', () => {
  const navegacao = {};
  const a = ambiente({ navegacao });
  a.avancar(300);
  navegacao.deliveryType = 'cache';
  a.carregar();
  assert.equal(a.camada.removido, true);
  assert.equal(a.principal.inert, false);
  a.avancar(20000);
  assert.equal(a.video.reproducoes, 1);
});

test('restauração do BFCache remove a sobreposição sem reproduzir novamente', () => {
  const a = ambiente();
  a.janela.dispatchEvent(new Event('pagehide'));
  const evento = new Event('pageshow');
  Object.defineProperty(evento, 'persisted', { value: true });
  a.janela.dispatchEvent(evento);
  a.avancar(20000);
  assert.equal(a.camada.removido, true);
  assert.equal(a.video.reproducoes, 1);
  assert.equal(a.principal.inert, false);
});

test('falha no autoplay mantém o progresso, sem trocar por imagem, e respeita o mínimo', async () => {
  const a = ambiente({ autoplayBloqueado: true });
  await Promise.resolve();
  assert.equal(a.camada.classList.contains('has-fallback'), false);
  a.carregar();
  a.avancar(1999);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.avancar(1031);
  assert.equal(a.camada.removido, true);
});

test('limite de carregamento e ausência de transitionend não deixam a página bloqueada', () => {
  const a = ambiente({ fontesCarregando: true });
  a.avancar(16030);
  assert.equal(a.camada.removido, true);
  assert.equal(a.principal.inert, false);
});

test('funciona com sessionStorage bloqueado', () => {
  const a = ambiente({ storageBloqueado: true });
  a.carregar();
  a.avancar(3030);
  assert.equal(a.camada.removido, true);
  assert.equal(a.principal.inert, false);
});

test('vídeo termina uma vez e conserva seu último frame durante a espera e o slide', () => {
  const a = ambiente();
  assert.equal(a.video.loop, false);
  a.avancar(4500);
  assert.equal(a.video.currentTime, a.video.duration);
  assert.equal(a.video.reproducoes, 1);
  assert.equal(a.video.pausas, 0);
  assert.equal(a.video.src, a.video.dataset.src);
  a.carregar();
  a.avancar(180);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
  assert.equal(a.video.currentTime, a.video.duration);
  assert.equal(a.video.src, a.video.dataset.src);
  a.terminarSlide();
  assert.equal(a.video.src, undefined);
});

test('aguarda o vídeo terminar se a reprodução começar ou terminar mais tarde', () => {
  const a = ambiente({ duracaoVideo: 16 });
  a.carregar();
  a.avancar(2180);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  assert.notEqual(a.porcentagem.textContent, '100%');
  a.avancar(1820);
  assert.equal(a.porcentagem.textContent, '100%');
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.avancar(180);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

test('barra e contador avançam juntos sem chegar a 100 antes da página estar pronta', () => {
  const a = ambiente();
  let anterior = 0;
  for (let i = 0; i < 8; i += 1) {
    a.avancar(250);
    const valor = Number(a.indicador.getAttribute('aria-valuenow'));
    assert.ok(valor > anterior && valor < 100);
    assert.equal(a.porcentagem.textContent, `${valor}%`);
    assert.equal(a.barra.style.transform, `scaleX(${valor / 100})`);
    anterior = valor;
  }
  a.avancar(1000);
  assert.equal(Number(a.indicador.getAttribute('aria-valuenow')), anterior);
  a.carregar();
  a.avancar(0);
  assert.equal(a.porcentagem.textContent, '100%');
  assert.equal(a.barra.style.transform, 'scaleX(1)');
});

test('erro no arquivo de vídeo libera o fluxo sem inserir logo estática', () => {
  const a = ambiente({ videoTravado: true });
  a.carregar();
  a.video.dispatchEvent(new Event('error'));
  a.avancar(2180);
  assert.equal(a.camada.classList.contains('has-fallback'), false);
  assert.equal(a.porcentagem.textContent, '100%');
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

test('vídeo travado tem limite de espera e não bloqueia a página', () => {
  const a = ambiente({ videoTravado: true });
  a.carregar();
  a.avancar(14999);
  assert.notEqual(a.porcentagem.textContent, '100%');
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.avancar(1031);
  assert.equal(a.camada.removido, true);
  assert.equal(a.principal.inert, false);
});

test('progresso continua válido sem metadados de duração', () => {
  const a = ambiente({ duracaoVideo: NaN });
  a.carregar();
  a.avancar(2200);
  assert.ok(Number.isFinite(Number(a.indicador.getAttribute('aria-valuenow'))));
  assert.notEqual(a.porcentagem.textContent, '100%');
  a.video.dispatchEvent(new Event('error'));
  a.avancar(180);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

test('sem elemento de vídeo a página ainda abre com progresso concluído', () => {
  const a = ambiente({ semVideo: true });
  a.carregar();
  a.avancar(2180);
  assert.equal(a.porcentagem.textContent, '100%');
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

test('ao sair da página os temporizadores de progresso e de conclusão são cancelados', () => {
  const a = ambiente();
  a.carregar();
  a.avancar(2000);
  a.janela.dispatchEvent(new Event('pagehide'));
  const progresso = a.porcentagem.textContent;
  a.avancar(20000);
  assert.equal(a.porcentagem.textContent, progresso);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  assert.equal(a.camada.removido, true);
});
