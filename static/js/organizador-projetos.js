document.addEventListener('DOMContentLoaded', () => {
  const formulario = document.querySelector('[data-organizer-form]');
  const lista = formulario?.querySelector('[data-project-list]');
  const botaoSalvar = formulario?.querySelector('[data-organizer-save]');
  const status = formulario?.querySelector('[data-organizer-status]');

  if (!formulario || !lista || !botaoSalvar || !status) {
    return;
  }

  let itemArrastado = null;
  let itemAlvo = null;

  const obterItens = () => Array.from(lista.querySelectorAll('[data-project-id]'));

  const atualizarInterface = () => {
    const itens = obterItens();

    itens.forEach((item, indice) => {
      const numero = item.querySelector('[data-order-number]');
      const botaoSubir = item.querySelector('[data-move="up"]');
      const botaoDescer = item.querySelector('[data-move="down"]');

      if (numero) {
        numero.textContent = String(indice + 1).padStart(2, '0');
      }
      if (botaoSubir) {
        botaoSubir.disabled = indice === 0;
      }
      if (botaoDescer) {
        botaoDescer.disabled = indice === itens.length - 1;
      }

      const destaque = item.querySelector('input[name="destaque"]');
      item.classList.toggle('is-featured', Boolean(destaque?.checked));
    });
  };

  const marcarComoAlterado = () => {
    formulario.classList.add('is-dirty');
    botaoSalvar.disabled = false;
    status.textContent = 'Existem alterações que ainda não foram salvas.';
  };

  lista.addEventListener('dragstart', (event) => {
    const alca = event.target.closest('.organizer-drag-handle');
    if (!alca) {
      return;
    }

    itemArrastado = alca.closest('[data-project-id]');
    itemArrastado.classList.add('is-dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', itemArrastado.dataset.projectId);
  });

  lista.addEventListener('dragover', (event) => {
    if (!itemArrastado) {
      return;
    }

    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    const novoAlvo = event.target.closest('[data-project-id]');

    if (novoAlvo === itemArrastado) {
      itemAlvo?.classList.remove('is-drop-target');
      itemAlvo = null;
      return;
    }

    if (!novoAlvo) {
      return;
    }

    itemAlvo?.classList.remove('is-drop-target');
    itemAlvo = novoAlvo;
    itemAlvo.classList.add('is-drop-target');
  });

  lista.addEventListener('drop', (event) => {
    if (!itemArrastado || !itemAlvo) {
      return;
    }

    event.preventDefault();
    const itens = obterItens();
    const indiceOrigem = itens.indexOf(itemArrastado);
    const indiceDestino = itens.indexOf(itemAlvo);

    lista.insertBefore(
      itemArrastado,
      indiceOrigem < indiceDestino ? itemAlvo.nextSibling : itemAlvo,
    );
    marcarComoAlterado();
    atualizarInterface();
  });

  lista.addEventListener('dragend', () => {
    itemArrastado?.classList.remove('is-dragging');
    itemAlvo?.classList.remove('is-drop-target');
    itemArrastado = null;
    itemAlvo = null;
  });

  lista.addEventListener('click', (event) => {
    const botao = event.target.closest('[data-move]');
    if (!botao) {
      return;
    }

    const item = botao.closest('[data-project-id]');
    const direcao = botao.dataset.move;

    if (direcao === 'up' && item.previousElementSibling) {
      lista.insertBefore(item, item.previousElementSibling);
    } else if (direcao === 'down' && item.nextElementSibling) {
      lista.insertBefore(item.nextElementSibling, item);
    } else {
      return;
    }

    marcarComoAlterado();
    atualizarInterface();
    botao.focus({ preventScroll: true });
  });

  lista.addEventListener('change', (event) => {
    if (!event.target.matches('input[name="destaque"]')) {
      return;
    }

    marcarComoAlterado();
    atualizarInterface();
  });

  formulario.addEventListener('submit', async (event) => {
    event.preventDefault();

    const itens = obterItens();
    const destaque = formulario.querySelector('input[name="destaque"]:checked');
    const csrfToken = formulario.querySelector('[name="csrfmiddlewaretoken"]')?.value;

    botaoSalvar.disabled = true;
    formulario.setAttribute('aria-busy', 'true');
    status.textContent = 'Salvando nova organização…';

    try {
      const resposta = await fetch(formulario.action, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          ordem: itens.map((item) => Number(item.dataset.projectId)),
          destaque: destaque ? Number(destaque.value) : null,
        }),
      });
      const dados = await resposta.json();

      if (!resposta.ok || !dados.ok) {
        throw new Error(dados.mensagem || 'Não foi possível salvar a organização.');
      }

      formulario.classList.remove('is-dirty');
      status.textContent = dados.mensagem;
    } catch (erro) {
      botaoSalvar.disabled = false;
      status.textContent = erro.message;
    } finally {
      formulario.removeAttribute('aria-busy');
    }
  });

  atualizarInterface();
});
