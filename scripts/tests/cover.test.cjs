const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const codigo = fs.readFileSync(path.join(__dirname, '../../static/js/cover.js'), 'utf8');
const matematica = vm.createContext({});
vm.runInContext(codigo, matematica);
const calcular = matematica.calcularInclinacaoSensor;

class Elemento extends EventTarget {
  constructor() {
    super();
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.atributos = new Map();
    this.filhos = new Map();
    this.valores = { x: 0, y: 0, rotationX: 0, rotationY: 0 };
    const classes = new Set();
    this.classList = {
      add: (nome) => classes.add(nome),
      remove: (nome) => classes.delete(nome),
      contains: (nome) => classes.has(nome),
    };
  }
  querySelector(seletor) { return this.filhos.get(seletor) ?? null; }
  setAttribute(nome, valor) { this.atributos.set(nome, valor); }
  getAttribute(nome) { return this.atributos.get(nome) ?? null; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100 }; }
}

function ambiente(opcoes = {}) {
  let agora = 0;
  let id = 0;
  const tarefas = new Map();
  const quadros = new Map();
  const elementos = Object.fromEntries([
    'capa', 'logo', 'titulo', 'projeto', 'apresentacao', 'arte', 'controle', 'botao', 'rotulo', 'status', 'descricao',
  ].map((nome) => [nome, new Elemento()]));
  const { capa, controle, botao, rotulo, status } = elementos;
  controle.hidden = true;
  const seletores = {
    '[data-cover-logo-tilt]': 'logo',
    '[data-cover-title]': 'titulo',
    '[data-cover-project-tilt]': 'projeto',
    '[data-cover-position]': 'apresentacao',
    '[data-cover-art]': 'arte',
    '[data-cover-motion]': 'controle',
  };
  for (const [seletor, nome] of Object.entries(seletores)) capa.filhos.set(seletor, elementos[nome]);
  controle.filhos.set('button', botao);
  controle.filhos.set('[data-cover-motion-label]', rotulo);
  controle.filhos.set('[data-cover-motion-status]', status);
  const documento = new EventTarget();
  documento.documentElement = new Elemento();
  documento.hidden = false;
  documento.querySelector = () => capa;
  const janela = new EventTarget();
  janela.isSecureContext = opcoes.seguro !== false;
  janela.screen = { orientation: new EventTarget() };
  janela.screen.orientation.angle = 0;
  let permissoes = 0;
  if (opcoes.suporte !== false) {
    janela.DeviceOrientationEvent = class {};
    if (opcoes.permissao !== undefined) {
      janela.DeviceOrientationEvent.requestPermission = () => {
        permissoes += 1;
        if (typeof opcoes.permissao === 'function') return opcoes.permissao();
        return Promise.resolve(opcoes.permissao);
      };
    }
  }
  let observar;
  let desconectou = false;
  janela.IntersectionObserver = class {
    constructor(callback) { observar = callback; }
    observe() {}
    disconnect() { desconectou = true; }
  };
  janela.setTimeout = (acao, atraso) => {
    const numero = ++id;
    tarefas.set(numero, { acao, tempo: agora + atraso });
    return numero;
  };
  janela.clearTimeout = (numero) => tarefas.delete(numero);
  janela.requestAnimationFrame = (acao) => { const numero = ++id; quadros.set(numero, acao); return numero; };
  janela.cancelAnimationFrame = (numero) => quadros.delete(numero);
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
  const renderizar = () => {
    const pendentes = [...quadros.values()];
    quadros.clear();
    pendentes.forEach((acao) => acao());
  };
  const contextos = [];
  let atual;
  let atualizacoes = 0;
  const media = {
    add(consultas, callback) {
      const conditions = Object.fromEntries(Object.entries(consultas).map(([nome, consulta]) => {
        let valor = false;
        if (consulta.includes('min-width')) valor = !!opcoes.desktop;
        if (consulta.includes('pointer: fine')) valor = !!opcoes.desktop;
        if (consulta.includes('pointer: coarse')) valor = !opcoes.desktop;
        if (consulta.includes('prefers-reduced-motion')) valor = !!opcoes.reduzir;
        return [nome, valor];
      }));
      if (!Object.values(conditions).some(Boolean)) return;
      const contexto = { alvos: new Set() };
      atual = contexto;
      contexto.limpar = callback({ conditions });
      atual = null;
      contextos.push(contexto);
    },
    revert() {
      for (const contexto of contextos.splice(0)) {
        contexto.limpar?.();
        contexto.alvos.forEach((alvo) => {
          Object.keys(alvo.valores).forEach((propriedade) => { alvo.valores[propriedade] = 0; });
        });
      }
    },
  };
  const gsap = {
    matchMedia: () => media,
    utils: { clamp: (minimo, maximo, valor) => Math.min(maximo, Math.max(minimo, valor)) },
    quickTo(alvo, propriedade) {
      atual?.alvos.add(alvo);
      return (valor) => { alvo.valores[propriedade] = valor; atualizacoes += 1; };
    },
  };
  janela.gsap = gsap;
  const contexto = vm.createContext({ window: janela, document: documento, gsap, AbortController });
  vm.runInContext(codigo, contexto);
  contexto.iniciarCapa();
  observar?.([{ isIntersecting: true }]);
  const orientar = (beta, gamma) => {
    const evento = new Event('deviceorientation');
    Object.assign(evento, { beta, gamma });
    janela.dispatchEvent(evento);
  };
  return {
    ...elementos, janela, documento, media, avancar, renderizar, orientar,
    clicar: async () => { botao.dispatchEvent(new Event('click')); await new Promise(setImmediate); },
    visibilidade: (visivel) => { documento.hidden = !visivel; documento.dispatchEvent(new Event('visibilitychange')); },
    mostrarCapa: (visivel) => observar?.([{ isIntersecting: visivel }]),
    girarTela: (angulo) => { janela.screen.orientation.angle = angulo; janela.screen.orientation.dispatchEvent(new Event('change')); },
    get permissoes() { return permissoes; },
    get quadros() { return quadros.size; },
    get atualizacoes() { return atualizacoes; },
    get desconectou() { return desconectou; },
    get temporizadores() { return tarefas.size; },
  };
}

test('a posição em que o telefone é segurado vira o centro e pequenos tremores são ignorados', () => {
  const referencia = { beta: 48, gamma: -12 };
  for (const leitura of [referencia, { beta: 48.2, gamma: -12.3 }]) {
    const resultado = calcular(leitura, referencia);
    assert.equal(Math.abs(resultado.x), 0);
    assert.equal(Math.abs(resultado.y), 0);
  }
});

test('as leituras são limitadas e compensam retrato, paisagem e tela invertida', () => {
  const referencia = { beta: 0, gamma: 0 };
  const evento = { beta: 22, gamma: 0 };
  for (const [angulo, x, y] of [[0, 0, 1], [90, 1, 0], [180, 0, -1], [270, -1, 0]]) {
    const resultado = calcular(evento, referencia, angulo);
    assert.equal(Math.round(resultado.x) || 0, x);
    assert.equal(Math.round(resultado.y) || 0, y);
  }
  const limite = calcular({ beta: 100, gamma: -80 }, referencia);
  assert.equal(limite.x, -1);
  assert.equal(limite.y, 1);
});

test('ângulos que atravessam 180 graus não provocam salto e dados ausentes são rejeitados', () => {
  const resultado = calcular({ beta: -179, gamma: 0 }, { beta: 179, gamma: 0 });
  assert.ok(resultado.y > 0 && resultado.y < 0.1);
  for (const evento of [{ beta: null, gamma: 0 }, { beta: 0, gamma: NaN }, { beta: Infinity, gamma: 0 }]) {
    assert.equal(calcular(evento, { beta: 0, gamma: 0 }), null);
  }
});

for (const [nome, opcoes] of [
  ['sem sensores', { suporte: false }],
  ['em HTTP inseguro', { seguro: false }],
  ['com movimento reduzido', { reduzir: true }],
  ['no desktop', { desktop: true }],
]) {
  test(`controle de sensores fica oculto ${nome}`, () => {
    const a = ambiente({ ...opcoes, permissao: 'granted' });
    assert.equal(a.controle.hidden, true);
    assert.equal(a.permissoes, 0);
    a.orientar(10, 10);
    assert.equal(a.quadros, 0);
  });
}

test('iOS só solicita permissão no toque e calibra a primeira leitura válida', async () => {
  const a = ambiente({ permissao: 'granted' });
  assert.equal(a.controle.hidden, false);
  assert.equal(a.permissoes, 0);
  await a.clicar();
  assert.equal(a.permissoes, 1);
  assert.equal(a.botao.getAttribute('aria-pressed'), 'true');
  a.orientar(45, -8);
  a.renderizar();
  assert.equal(Math.abs(a.titulo.valores.rotationY), 0);
  a.orientar(67, 14);
  a.renderizar();
  assert.equal(a.logo.valores.rotationY, 5);
  assert.equal(a.titulo.valores.rotationX, -5);
  assert.equal(a.projeto.valores.rotationY, 7);
  assert.equal(a.descricao.valores.rotationY, 0);
});

test('Android sem requestPermission também espera o visitante ativar o efeito', async () => {
  const a = ambiente();
  a.orientar(0, 0);
  assert.equal(a.quadros, 0);
  await a.clicar();
  a.orientar(0, 0);
  a.orientar(0, 22);
  a.renderizar();
  assert.equal(a.titulo.valores.rotationY, 5);
});

for (const [nome, permissao] of [
  ['negada', 'denied'],
  ['com erro', () => Promise.reject(new Error('Bloqueado'))],
]) {
  test(`permissão ${nome} mantém a página estática e o botão disponível`, async () => {
    const a = ambiente({ permissao });
    await a.clicar();
    assert.equal(a.botao.getAttribute('aria-pressed'), 'false');
    assert.equal(a.botao.disabled, false);
    assert.ok(a.status.textContent.length > 0);
    a.orientar(30, 30);
    assert.equal(a.quadros, 0);
  });
}

test('nenhum dado válido em cinco segundos desativa a leitura sem bloquear a navegação', async () => {
  const a = ambiente();
  await a.clicar();
  a.orientar(null, null);
  a.avancar(5000);
  assert.equal(a.botao.getAttribute('aria-pressed'), 'false');
  assert.match(a.status.textContent, /indisponível/);
  a.orientar(0, 0);
  assert.equal(a.quadros, 0);
});

test('uma leitura válida cancela o limite de espera', async () => {
  const a = ambiente();
  await a.clicar();
  a.orientar(40, 0);
  a.renderizar();
  a.avancar(10000);
  assert.equal(a.botao.getAttribute('aria-pressed'), 'true');
});

test('muitos eventos entre dois frames resultam em uma atualização com a última leitura', async () => {
  const a = ambiente();
  await a.clicar();
  a.orientar(0, 0);
  a.renderizar();
  const antes = a.atualizacoes;
  for (let i = 0; i < 100; i += 1) a.orientar(22, 22);
  assert.equal(a.quadros, 1);
  a.renderizar();
  assert.equal(a.atualizacoes - antes, 12);
  assert.equal(a.projeto.valores.rotationX, -7);
});

for (const tipo of ['capa', 'aba']) {
  test(`pausa fora da ${tipo} e recalibra quando o visitante volta`, async () => {
    const a = ambiente();
    await a.clicar();
    a.orientar(0, 0);
    a.orientar(22, 22);
    a.renderizar();
    const visibilidade = tipo === 'capa' ? a.mostrarCapa : a.visibilidade;
    visibilidade(false);
    assert.equal(a.titulo.valores.rotationY, 0);
    a.orientar(80, 80);
    assert.equal(a.quadros, 0);
    visibilidade(true);
    a.orientar(60, -10);
    a.renderizar();
    assert.equal(Math.abs(a.titulo.valores.rotationY), 0);
  });
}

test('desativar pelo botão restaura a composição e permite ativar novamente', async () => {
  const a = ambiente();
  await a.clicar();
  a.orientar(0, 0);
  a.orientar(22, 22);
  a.renderizar();
  await a.clicar();
  assert.equal(a.botao.getAttribute('aria-pressed'), 'false');
  assert.equal(a.logo.valores.rotationY, 0);
  a.orientar(0, 0);
  assert.equal(a.quadros, 0);
  await a.clicar();
  a.orientar(45, 10);
  a.renderizar();
  assert.equal(Math.abs(a.logo.valores.rotationY), 0);
});

test('girar a tela recalibra e troca os eixos da inclinação', async () => {
  const a = ambiente();
  await a.clicar();
  a.orientar(0, 0);
  a.girarTela(90);
  a.orientar(45, -15);
  a.renderizar();
  assert.equal(Math.abs(a.logo.valores.rotationY), 0);
  a.orientar(67, -15);
  a.renderizar();
  assert.equal(a.logo.valores.rotationY, 5);
  assert.equal(Math.abs(a.logo.valores.rotationX), 0);
});

test('o sensor só começa depois da conclusão do preloader', async () => {
  const a = ambiente();
  a.documento.documentElement.classList.add('is-preloading');
  await a.clicar();
  a.orientar(0, 0);
  assert.equal(a.quadros, 0);
  a.documento.documentElement.classList.remove('is-preloading');
  a.janela.dispatchEvent(new Event('preloader:complete'));
  a.orientar(0, 0);
  a.orientar(22, 22);
  a.renderizar();
  assert.equal(a.logo.valores.rotationY, 5);
});

test('BFCache pausa e retoma os sensores sem novo pedido de permissão', async () => {
  const a = ambiente({ permissao: 'granted' });
  await a.clicar();
  const evento = new Event('pagehide');
  Object.assign(evento, { persisted: true });
  a.janela.dispatchEvent(evento);
  a.orientar(0, 0);
  assert.equal(a.quadros, 0);
  a.janela.dispatchEvent(new Event('pageshow'));
  a.orientar(10, 10);
  a.renderizar();
  assert.equal(a.permissoes, 1);
  assert.equal(Math.abs(a.logo.valores.rotationY), 0);
});

test('limpeza cancela sensores, observador, frames e temporizadores', async () => {
  const a = ambiente();
  await a.clicar();
  a.orientar(0, 0);
  a.media.revert();
  assert.equal(a.desconectou, true);
  assert.equal(a.controle.hidden, true);
  assert.equal(a.quadros, 0);
  assert.equal(a.temporizadores, 0);
  a.orientar(30, 30);
  assert.equal(a.quadros, 0);
});

test('permissão pendente que resolve depois da limpeza não reativa o efeito', async () => {
  let conceder;
  const permissao = new Promise((resolve) => { conceder = resolve; });
  const a = ambiente({ permissao: () => permissao });
  await a.clicar();
  a.media.revert();
  conceder('granted');
  await new Promise(setImmediate);
  assert.equal(a.controle.hidden, true);
  assert.equal(a.botao.getAttribute('aria-pressed'), 'false');
  a.orientar(0, 0);
  assert.equal(a.quadros, 0);
});

test('no desktop o mouse mantém nome/logo e card independentes e textos fixos', () => {
  const a = ambiente({ desktop: true });
  const mover = (alvo, tipo = 'mouse') => {
    const evento = new Event('pointermove');
    Object.assign(evento, { clientX: 100, clientY: 100, pointerType: tipo });
    alvo.dispatchEvent(evento);
  };
  mover(a.apresentacao);
  assert.equal(a.logo.valores.rotationY, 7);
  assert.equal(a.titulo.valores.rotationX, -7);
  assert.equal(a.projeto.valores.rotationY, 0);
  assert.equal(a.descricao.valores.rotationY, 0);
  mover(a.arte);
  assert.equal(a.projeto.valores.rotationY, 9);
  a.apresentacao.dispatchEvent(new Event('pointerleave'));
  assert.equal(a.titulo.valores.rotationY, 0);
  assert.equal(a.projeto.valores.rotationY, 9);
  mover(a.apresentacao, 'touch');
  assert.equal(a.titulo.valores.rotationY, 0);
});
