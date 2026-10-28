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
  const video = new Elemento();
  video.dataset = { src: '/static/videos/hv-preloader.webm' };
  video.reproducoes = 0;
  video.pausas = 0;
  video.load = () => {};
  video.pause = () => { video.pausas += 1; };
  video.play = () => {
    video.reproducoes += 1;
    return opcoes.autoplayBloqueado ? Promise.reject(new Error('Autoplay bloqueado')) : Promise.resolve();
  };
  camada.querySelector = () => video;
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
  const avancar = (tempo) => {
    const destino = agora + tempo;
    while (true) {
      const proxima = [...tarefas.entries()].filter(([, t]) => t.tempo <= destino)
        .sort((a, b) => a[1].tempo - b[1].tempo)[0];
      if (!proxima) break;
      tarefas.delete(proxima[0]);
      agora = proxima[1].tempo;
      proxima[1].acao();
    }
    agora = destino;
  };
  const controle = contexto.iniciarPreloader(janela);
  controle.montar();
  documento.dispatchEvent(new Event('DOMContentLoaded'));
  return {
    janela, documento, camada, video, principal, nav, valores, avancar,
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
  a.avancar(0);
  assert.equal(a.camada.classList.contains('is-leaving'), true);
});

test('aguarda as fontes antes de abrir a página', async () => {
  const a = ambiente({ fontesCarregando: true });
  a.carregar();
  a.avancar(2100);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.fontesProntas();
  await Promise.resolve();
  a.avancar(0);
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

test('falha no autoplay mostra a marca estática e respeita o mínimo', async () => {
  const a = ambiente({ autoplayBloqueado: true });
  await Promise.resolve();
  assert.equal(a.camada.classList.contains('has-fallback'), true);
  a.carregar();
  a.avancar(1999);
  assert.equal(a.camada.classList.contains('is-leaving'), false);
  a.avancar(851);
  assert.equal(a.camada.removido, true);
});

test('limite de carregamento e ausência de transitionend não deixam a página bloqueada', () => {
  const a = ambiente({ fontesCarregando: true });
  a.avancar(15850);
  assert.equal(a.camada.removido, true);
  assert.equal(a.principal.inert, false);
});

test('funciona com sessionStorage bloqueado', () => {
  const a = ambiente({ storageBloqueado: true });
  a.carregar();
  a.avancar(2850);
  assert.equal(a.camada.removido, true);
  assert.equal(a.principal.inert, false);
});
