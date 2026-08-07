document.addEventListener('DOMContentLoaded', () => {
  const tiposPermitidos = new Set(['image/png', 'image/jpeg', 'image/webp']);
  const extensoesPermitidas = new Set(['png', 'jpg', 'jpeg', 'webp']);

  document.querySelectorAll('[data-capa-upload]').forEach((componente) => {
    const input = componente.querySelector('[data-capa-input]');
    const dropzone = componente.querySelector('[data-capa-dropzone]');
    const titulo = componente.querySelector('[data-capa-dropzone-title]');
    const erro = componente.querySelector('[data-capa-error]');
    const preview = componente.querySelector('[data-capa-preview]');
    const previewImg = componente.querySelector('[data-capa-preview-img]');
    const status = componente.querySelector('[data-capa-status]');
    const capaOriginal = preview.dataset.capaOriginal || '';
    let urlTemporaria = null;
    let eventosDeArraste = 0;

    const arquivoPermitido = (arquivo) => {
      const extensao = arquivo.name.split('.').pop().toLowerCase();
      return tiposPermitidos.has(arquivo.type) || extensoesPermitidas.has(extensao);
    };

    const limparUrlTemporaria = () => {
      if (urlTemporaria) {
        URL.revokeObjectURL(urlTemporaria);
        urlTemporaria = null;
      }
    };

    const restaurarPreview = () => {
      limparUrlTemporaria();
      titulo.textContent = 'Arraste a imagem aqui ou clique para selecionar';

      if (capaOriginal) {
        previewImg.src = capaOriginal;
        status.textContent = 'Capa atual';
        preview.classList.remove('is-hidden');
      } else {
        previewImg.removeAttribute('src');
        preview.classList.add('is-hidden');
      }
    };

    const exibirArquivo = (arquivo) => {
      erro.hidden = true;
      limparUrlTemporaria();
      urlTemporaria = URL.createObjectURL(arquivo);
      previewImg.src = urlTemporaria;
      preview.classList.remove('is-hidden');
      status.textContent = 'Nova capa (pré-visualização)';
      titulo.textContent = arquivo.name;
    };

    const validarArquivo = (arquivo) => {
      if (!arquivoPermitido(arquivo)) {
        input.value = '';
        erro.textContent = 'Formato inválido. Selecione uma imagem PNG, JPEG ou WebP.';
        erro.hidden = false;
        restaurarPreview();
        return false;
      }

      exibirArquivo(arquivo);
      return true;
    };

    input.addEventListener('change', () => {
      const [arquivo] = input.files;
      if (arquivo) {
        validarArquivo(arquivo);
      } else {
        erro.hidden = true;
        restaurarPreview();
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
      const [arquivo] = event.dataTransfer.files;

      if (!arquivo || !validarArquivo(arquivo)) {
        return;
      }

      const transferencia = new DataTransfer();
      transferencia.items.add(arquivo);
      input.files = transferencia.files;
    });

    window.addEventListener('beforeunload', limparUrlTemporaria);
  });
});
