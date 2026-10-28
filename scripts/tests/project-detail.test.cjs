const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ler = (nome) => fs.readFileSync(path.join(__dirname, '../../static/js', nome), 'utf8');

class Elemento extends EventTarget {
  constructor() {
    super();
    this.hidden = true;
    this.atributos = new Map();
    this.filhos = new Map();
    this.textContent = '';
    const classes = new Set();
    this.classList = {
      add: (nome) => classes.add(nome),
      remove: (nome) => classes.delete(nome),
      contains: (nome) => classes.has(nome),
    };
  }
  setAttribute(nome, valor) { this.atributos.set(nome, valor); }
  getAttribute(nome) { return this.atributos.get(nome); }
  querySelector(seletor) { return this.filhos.get(seletor) ?? null; }
  contains(elemento) { return elemento === this || elemento === this.link; }
}

function acesso(opcoes = {}) {
  const documento = new Elemento();
  documento.hidden = false;
  const principal = new Elemento();
  const barra = new Elemento();
  barra.link = new Elemento();
  if (!opcoes.semUrl) {
    documento.filhos.set('[data-project-primary-access]', principal);
    documento.filhos.set('[data-project-launchbar]', barra);
  }
  let callback;
  let desconectou = false;
  const janela = { document: documento, queueMicrotask };
  if (!opcoes.semObservador) {
    janela.IntersectionObserver = class {
      constructor(acao) { callback = acao; }
      observe(alvo) { assert.equal(alvo, principal); }
      disconnect() { desconectou = true; }
    };
  }
  const contexto = vm.createContext({});
  vm.runInContext(ler('project-detail.js'), contexto);
  const limpar = contexto.iniciarAcessoRapidoProjeto(janela);
  return {
    barra, documento, limpar,
    visivel: (fracao) => callback?.([{ isIntersecting: fracao > 0, intersectionRatio: fracao }]),
    get desconectou() { return desconectou; },
  };
}

test('atalho aparece apenas quando o botão inicial não está totalmente visível', () => {
  const a = acesso();
  a.visivel(1);
  assert.equal(a.barra.hidden, true);
  a.visivel(0.5);
  assert.equal(a.barra.hidden, false);
  a.visivel(0);
  assert.equal(a.barra.hidden, false);
  a.visivel(1);
  assert.equal(a.barra.hidden, true);
});

test('não há dependência de sensores, GSAP ou observadores para os links originais', () => {
  assert.equal(acesso({ semUrl: true }).limpar, undefined);
  const a = acesso({ semObservador: true });
  assert.equal(a.limpar, undefined);
  assert.equal(a.barra.hidden, true);
});

test('atalho fica oculto com a aba em segundo plano e volta quando necessário', () => {
  const a = acesso();
  a.visivel(0);
  a.documento.activeElement = a.barra.link;
  a.documento.hidden = true;
  a.documento.dispatchEvent(new Event('visibilitychange'));
  assert.equal(a.barra.hidden, true);
  a.documento.hidden = false;
  a.documento.dispatchEvent(new Event('visibilitychange'));
  assert.equal(a.barra.hidden, false);
});

test('rolar até o botão inicial não esconde um atalho que mantém foco do teclado', async () => {
  const a = acesso();
  a.visivel(0);
  a.documento.activeElement = a.barra.link;
  a.visivel(1);
  assert.equal(a.barra.hidden, false);
  a.documento.activeElement = null;
  a.barra.dispatchEvent(new Event('focusout'));
  await Promise.resolve();
  assert.equal(a.barra.hidden, true);
});

test('limpeza desconecta o observador e ignora atualizações tardias', () => {
  const a = acesso();
  a.visivel(0);
  a.limpar();
  assert.equal(a.desconectou, true);
  a.visivel(0);
  assert.equal(a.barra.hidden, true);
});

function galeria() {
  const raiz = new Elemento();
  const anterior = new Elemento();
  const proximo = new Elemento();
  const contador = new Elemento();
  const ampliar = new Elemento();
  const slides = ['/media/primeira.webp', '/media/segunda.webp'].map((src, indice) => {
    const slide = new Elemento();
    const imagem = new Elemento();
    imagem.setAttribute('src', src);
    slide.filhos.set('[data-project-image]', imagem);
    slide.setAttribute('aria-hidden', String(indice !== 0));
    if (indice === 0) slide.classList.add('is-active');
    return slide;
  });
  raiz.querySelectorAll = () => slides;
  for (const [seletor, elemento] of Object.entries({
    '[data-project-carousel-previous]': anterior,
    '[data-project-carousel-next]': proximo,
    '[data-project-carousel-current]': contador,
    '[data-project-image-link]': ampliar,
  })) raiz.filhos.set(seletor, elemento);
  ampliar.setAttribute('href', '/media/primeira.webp');
  const documento = new Elemento();
  documento.filhos.set('[data-project-carousel]', raiz);
  const contexto = vm.createContext({ document: documento });
  vm.runInContext(ler('site.js'), contexto);
  contexto.iniciarCarrosselProjeto({ movimentoReduzido: true });
  return { raiz, anterior, proximo, contador, ampliar, slides };
}

test('trocar imagem atualiza a prévia, o contador e o destino de ampliar imagem', () => {
  const a = galeria();
  a.proximo.dispatchEvent(new Event('click'));
  assert.equal(a.contador.textContent, '02');
  assert.equal(a.ampliar.getAttribute('href'), '/media/segunda.webp');
  assert.equal(a.slides[0].getAttribute('aria-hidden'), 'true');
  assert.equal(a.slides[1].getAttribute('aria-hidden'), 'false');
  assert.equal(a.slides[1].classList.contains('is-active'), true);
  a.anterior.dispatchEvent(new Event('click'));
  assert.equal(a.ampliar.getAttribute('href'), '/media/primeira.webp');
});

test('galeria continua funcionando por teclado, sem GSAP e com navegação circular', () => {
  const a = galeria();
  const tecla = new Event('keydown', { cancelable: true });
  Object.defineProperty(tecla, 'key', { value: 'ArrowLeft' });
  a.raiz.dispatchEvent(tecla);
  assert.equal(tecla.defaultPrevented, true);
  assert.equal(a.contador.textContent, '02');
  a.proximo.dispatchEvent(new Event('click'));
  assert.equal(a.contador.textContent, '01');
  assert.equal(a.ampliar.getAttribute('href'), '/media/primeira.webp');
});
