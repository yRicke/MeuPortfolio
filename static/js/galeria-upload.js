document.addEventListener('DOMContentLoaded', () => {
  const tiposPermitidos = new Set(['image/png', 'image/jpeg', 'image/webp']);
  const extensoesPermitidas = new Set(['png', 'jpg', 'jpeg', 'webp']);

  document.querySelectorAll('[data-gallery-upload]').forEach((componente) => {
    const input = componente.querySelector('[data-gallery-input]');
    const dropzone = componente.querySelector('[data-gallery-dropzone]');
    const titulo = componente.querySelector('[data-gallery-title]');
    const erro = componente.querySelector('[data-gallery-error]');
    const preview = componente.querySelector('[data-gallery-preview]');
    let urlsTemporarias = [];
    let eventosDeArraste = 0;

    const arquivoPermitido = (arquivo) => {
      const extensao = arquivo.name.split('.').pop().toLowerCase();
      return tiposPermitidos.has(arquivo.type) || extensoesPermitidas.has(extensao);
    };

    const limparUrls = () => {
      urlsTemporarias.forEach((url) => URL.revokeObjectURL(url));
      urlsTemporarias = [];
    };

    const limparPreview = () => {
      limparUrls();
      preview.replaceChildren();
      preview.classList.add('is-hidden');
      titulo.textContent = 'Arraste as imagens aqui ou clique para selecionar';
    };

    const exibirArquivos = (arquivos) => {
      limparPreview();

      arquivos.forEach((arquivo, indice) => {
        const url = URL.createObjectURL(arquivo);
        const item = document.createElement('figure');
        const imagem = document.createElement('img');
        const legenda = document.createElement('figcaption');

        urlsTemporarias.push(url);
        item.className = 'gallery-preview-item';
        imagem.src = url;
        imagem.alt = `Pré-visualização da imagem ${indice + 1}`;
        legenda.textContent = arquivo.name;
        item.append(imagem, legenda);
        preview.append(item);
      });

      preview.classList.remove('is-hidden');
      titulo.textContent = `${arquivos.length} imagem(ns) selecionada(s)`;
    };

    const validarArquivos = (listaDeArquivos) => {
      const arquivos = Array.from(listaDeArquivos);
      const invalido = arquivos.find((arquivo) => !arquivoPermitido(arquivo));

      if (invalido) {
        input.value = '';
        erro.textContent = `Formato inválido em “${invalido.name}”. Use PNG, JPEG ou WebP.`;
        erro.hidden = false;
        limparPreview();
        return [];
      }

      erro.hidden = true;
      exibirArquivos(arquivos);
      return arquivos;
    };

    input.addEventListener('change', () => {
      if (input.files.length) {
        validarArquivos(input.files);
      } else {
        erro.hidden = true;
        limparPreview();
      }
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((evento) => {
      dropzone.addEventListener(evento, (event) => {
        event.preventDefault();
        event.stopPropagation();
      });
    });

    dropzone.addEventListener('dragenter', () => {
      eventosDeArraste += 1;
      dropzone.classList.add('is-dragging');
    });

    dropzone.addEventListener('dragleave', () => {
      eventosDeArraste -= 1;
      if (eventosDeArraste <= 0) {
        eventosDeArraste = 0;
        dropzone.classList.remove('is-dragging');
      }
    });

    dropzone.addEventListener('drop', (event) => {
      eventosDeArraste = 0;
      dropzone.classList.remove('is-dragging');
      const arquivos = validarArquivos(event.dataTransfer.files);

      if (!arquivos.length) {
        return;
      }

      const transferencia = new DataTransfer();
      arquivos.forEach((arquivo) => transferencia.items.add(arquivo));
      input.files = transferencia.files;
    });

    window.addEventListener('beforeunload', limparUrls);
  });
});
