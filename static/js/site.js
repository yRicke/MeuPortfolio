document.addEventListener('DOMContentLoaded', () => {
  const nav = document.querySelector('[data-site-nav]');
  const movimentoReduzido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const atualizarNav = () => {
    nav?.classList.toggle('is-scrolled', window.scrollY > 24);
  };

  atualizarNav();
  window.addEventListener('scroll', atualizarNav, { passive: true });

  document.querySelectorAll('[data-image-frame]').forEach((moldura) => {
    const imagem = moldura.querySelector('[data-project-image]');
    if (!imagem) {
      moldura.classList.add('is-missing');
      return;
    }

    const mostrarFallback = () => moldura.classList.add('is-missing');
    const mostrarImagem = () => moldura.classList.remove('is-missing');
    imagem.addEventListener('error', mostrarFallback);
    imagem.addEventListener('load', mostrarImagem);

    if (imagem.complete) {
      imagem.naturalWidth ? mostrarImagem() : mostrarFallback();
    }
  });

  iniciarCarrosselProjeto({
    movimentoReduzido,
    motorAnimacao: window.gsap,
  });

  const gsapDisponivel = window.gsap && window.ScrollTrigger && window.ScrollToPlugin;
  if (!gsapDisponivel) {
    return;
  }

  gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
  document.documentElement.classList.add('has-gsap-scroll');

  let tweenDeNavegacao = null;

  const encontrarDestino = (url) => {
    const mesmaPagina = url.origin === window.location.origin
      && url.pathname === window.location.pathname;

    if (!mesmaPagina || !url.hash) {
      return null;
    }

    return document.getElementById(decodeURIComponent(url.hash.slice(1)));
  };

  document.querySelectorAll('[data-anchor-link]').forEach((link) => {
    link.addEventListener('click', (event) => {
      const destinoUrl = new URL(link.href, window.location.href);
      const destino = encontrarDestino(destinoUrl);

      if (!destino) {
        return;
      }

      event.preventDefault();
      history.replaceState(null, '', destinoUrl.hash);
      tweenDeNavegacao?.kill();
      tweenDeNavegacao = gsap.to(window, {
        duration: movimentoReduzido ? 0 : 1.4,
        scrollTo: { y: destino, offsetY: 0 },
        ease: 'power4.out',
        overwrite: true,
        onComplete: () => {
          tweenDeNavegacao = null;
        },
        onInterrupt: () => {
          tweenDeNavegacao = null;
        },
      });
    });
  });

  const transicao = document.querySelector('[data-page-transition]');
  if (transicao && !movimentoReduzido) {
    gsap.fromTo(
      transicao,
      { scaleY: 1, transformOrigin: 'top' },
      { scaleY: 0, duration: 0.85, ease: 'power4.inOut' },
    );
  }

  document.querySelectorAll('[data-reveal]').forEach((elemento) => {
    gsap.from(elemento, {
      y: movimentoReduzido ? 0 : 70,
      autoAlpha: 0,
      duration: movimentoReduzido ? 0.01 : 1.15,
      ease: 'power3.out',
      scrollTrigger: {
        trigger: elemento,
        start: 'top 84%',
        once: true,
      },
    });
  });

  const paginaPortfolio = document.querySelector('[data-portfolio-page]');
  if (paginaPortfolio) {
    iniciarPortfolio({ movimentoReduzido });
  }

  const detalhe = document.querySelector('[data-project-detail]');
  if (detalhe && !movimentoReduzido) {
    const timeline = gsap.timeline({ defaults: { ease: 'power3.out' } });
    timeline
      .from('.project-detail-hero-chrome > *', {
        y: -12,
        autoAlpha: 0,
        duration: 0.65,
        stagger: 0.08,
      })
      .from('.project-detail-slide.is-active .project-detail-media', {
        clipPath: 'inset(0 0 100% 0)',
        duration: 1.2,
      }, '-=0.4')
      .from('.project-detail-slide.is-active .project-detail-media img', {
        scale: 1.16,
        duration: 1.5,
      }, '<')
      .from('.project-detail-title > *', {
        y: 45,
        autoAlpha: 0,
        stagger: 0.12,
      }, '-=0.7')
      .from('.project-detail-carousel-controls', {
        autoAlpha: 0,
        duration: 0.6,
      }, '-=0.45');

    gsap.to('.project-detail-slide.is-active .project-detail-media img', {
      yPercent: 7,
      ease: 'none',
      scrollTrigger: {
        trigger: '.project-detail-hero',
        start: 'top top',
        end: 'bottom top',
        scrub: 0.9,
      },
    });

    gsap.to('.project-detail-title', {
      yPercent: 16,
      autoAlpha: 0.18,
      ease: 'none',
      scrollTrigger: {
        trigger: '.project-detail-hero',
        start: 'top top',
        end: 'bottom 35%',
        scrub: 0.8,
      },
    });
  }

  window.addEventListener('load', () => ScrollTrigger.refresh());
});

function iniciarCarrosselProjeto({ movimentoReduzido, motorAnimacao }) {
  const carrossel = document.querySelector('[data-project-carousel]');
  const slides = Array.from(carrossel?.querySelectorAll('[data-project-slide]') || []);
  const anterior = carrossel?.querySelector('[data-project-carousel-previous]');
  const proximo = carrossel?.querySelector('[data-project-carousel-next]');
  const contador = carrossel?.querySelector('[data-project-carousel-current]');

  if (!carrossel || slides.length < 2 || !anterior || !proximo) {
    return;
  }

  let indiceAtual = 0;
  let emTransicao = false;
  let ponteiroAtivo = null;
  let origemX = 0;
  let origemY = 0;
  let deslocamentoX = 0;
  let arrasteHorizontal = false;

  carrossel.classList.add('is-draggable');

  const atualizarContador = () => {
    if (contador) {
      contador.textContent = String(indiceAtual + 1).padStart(2, '0');
    }
  };

  const concluirTroca = (slideAtual, slideSeguinte) => {
    slideAtual.classList.remove('is-active');
    slideSeguinte.classList.add('is-active');
    motorAnimacao?.set([slideAtual, slideSeguinte], { clearProps: 'all' });
    emTransicao = false;
  };

  const navegar = (direcao) => {
    if (emTransicao) {
      return;
    }

    const proximoIndice = (indiceAtual + direcao + slides.length) % slides.length;
    const slideAtual = slides[indiceAtual];
    const slideSeguinte = slides[proximoIndice];

    indiceAtual = proximoIndice;
    atualizarContador();
    slideAtual.setAttribute('aria-hidden', 'true');
    slideSeguinte.setAttribute('aria-hidden', 'false');

    if (movimentoReduzido || !motorAnimacao) {
      concluirTroca(slideAtual, slideSeguinte);
      return;
    }

    emTransicao = true;
    slideSeguinte.classList.add('is-active');
    motorAnimacao.set(slideSeguinte, {
      xPercent: direcao * 100,
      autoAlpha: 1,
    });

    motorAnimacao.timeline({
      defaults: { duration: 0.9, ease: 'power4.out' },
      onComplete: () => concluirTroca(slideAtual, slideSeguinte),
    })
      .to(slideAtual, {
        xPercent: direcao * -18,
        autoAlpha: 0,
      })
      .to(slideSeguinte, { xPercent: 0 }, '<');
  };

  anterior.addEventListener('click', () => navegar(-1));
  proximo.addEventListener('click', () => navegar(1));
  carrossel.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      navegar(-1);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      navegar(1);
    }
  });

  carrossel.addEventListener('dragstart', (event) => event.preventDefault());
  carrossel.addEventListener('pointerdown', (event) => {
    const iniciouEmControle = event.target.closest('button, a');
    const botaoInvalido = event.pointerType === 'mouse' && event.button !== 0;

    if (emTransicao || iniciouEmControle || botaoInvalido) {
      return;
    }

    ponteiroAtivo = event.pointerId;
    origemX = event.clientX;
    origemY = event.clientY;
    deslocamentoX = 0;
    arrasteHorizontal = false;
  });

  carrossel.addEventListener('pointermove', (event) => {
    if (event.pointerId !== ponteiroAtivo) {
      return;
    }

    const distanciaX = event.clientX - origemX;
    const distanciaY = event.clientY - origemY;

    if (!arrasteHorizontal) {
      if (Math.abs(distanciaX) < 10 && Math.abs(distanciaY) < 10) {
        return;
      }

      if (Math.abs(distanciaY) >= Math.abs(distanciaX)) {
        ponteiroAtivo = null;
        return;
      }

      arrasteHorizontal = true;
      carrossel.classList.add('is-dragging');
      carrossel.setPointerCapture(event.pointerId);
    }

    event.preventDefault();
    deslocamentoX = distanciaX;
    motorAnimacao?.set(slides[indiceAtual], {
      x: deslocamentoX * 0.22,
    });
  });

  const finalizarArraste = (event, permitirNavegacao) => {
    if (event.pointerId !== ponteiroAtivo) {
      return;
    }

    const slideAtual = slides[indiceAtual];
    const limite = Math.min(90, carrossel.clientWidth * 0.14);
    const deveNavegar = (
      permitirNavegacao
      && arrasteHorizontal
      && Math.abs(deslocamentoX) >= limite
    );

    if (carrossel.hasPointerCapture(event.pointerId)) {
      carrossel.releasePointerCapture(event.pointerId);
    }

    carrossel.classList.remove('is-dragging');
    ponteiroAtivo = null;
    arrasteHorizontal = false;

    if (deveNavegar) {
      navegar(deslocamentoX < 0 ? 1 : -1);
    } else {
      motorAnimacao?.to(slideAtual, {
        x: 0,
        duration: movimentoReduzido ? 0 : 0.35,
        ease: 'power3.out',
      });
    }

    deslocamentoX = 0;
  };

  carrossel.addEventListener('pointerup', (event) => {
    finalizarArraste(event, true);
  });
  carrossel.addEventListener('pointercancel', (event) => {
    finalizarArraste(event, false);
  });
}

function iniciarPortfolio({ movimentoReduzido }) {
  const capa = document.querySelector('.cover-section');
  const arte = document.querySelector('[data-cover-art]');
  const secaoProjetos = document.querySelector('[data-horizontal-section]');
  const viewport = document.querySelector('[data-projects-viewport]');
  const trilho = document.querySelector('[data-projects-track]');
  const progresso = document.querySelector('[data-project-progress]');

  const animarCortina = (seletor) => {
    const cortina = document.querySelector(seletor);
    if (!cortina) {
      return;
    }

    if (movimentoReduzido) {
      gsap.set(cortina, { scaleY: 0 });
      return;
    }

    gsap.fromTo(
      cortina,
      { scaleY: 1, transformOrigin: 'top' },
      {
        scaleY: 0,
        transformOrigin: 'top',
        ease: 'none',
        scrollTrigger: {
          trigger: cortina.parentElement,
          start: 'top 92%',
          end: 'top 18%',
          scrub: 0.8,
          invalidateOnRefresh: true,
        },
      },
    );
  };

  if (!movimentoReduzido) {
    const entrada = gsap.timeline({ defaults: { ease: 'power4.out' } });
    entrada
      .from('[data-hero-logo]', {
        scale: 0.82,
        rotate: -10,
        autoAlpha: 0,
        duration: 1.5,
      }, 0)
      .from('[data-hero-line]', {
        yPercent: 115,
        rotate: 3,
        duration: 1.25,
        stagger: 0.1,
      }, 0.08)
      .from('[data-cover-art]', {
        clipPath: 'inset(100% 0 0 0)',
        duration: 1.35,
      }, '-=1')
      .from('[data-cover-art] img', {
        scale: 1.22,
        duration: 1.7,
      }, '<')
      .from('[data-hero-item]', {
        y: 24,
        autoAlpha: 0,
        duration: 0.8,
        stagger: 0.09,
      }, '-=0.75');
  }

  if (!movimentoReduzido) {
    gsap.to('[data-cover-orbit]', {
      rotate: 35,
      scale: 1.12,
      ease: 'none',
      scrollTrigger: {
        trigger: capa,
        start: 'top top',
        end: 'bottom top',
        scrub: 1,
      },
    });

    gsap.to(arte, {
      yPercent: 12,
      ease: 'none',
      scrollTrigger: {
        trigger: capa,
        start: 'top top',
        end: 'bottom top',
        scrub: 0.8,
      },
    });

    if (window.matchMedia('(pointer: fine)').matches && arte) {
      const moverX = gsap.quickTo(arte, 'x', { duration: 0.8, ease: 'power3' });
      const moverY = gsap.quickTo(arte, 'y', { duration: 0.8, ease: 'power3' });
      capa.addEventListener('pointermove', (event) => {
        moverX((event.clientX / window.innerWidth - 0.5) * 18);
        moverY((event.clientY / window.innerHeight - 0.5) * 18);
      });
    }
  }

  animarCortina('.projects-curtain');

  if (!movimentoReduzido) {
    gsap.from('.projects-heading > *', {
      y: 36,
      autoAlpha: 0,
      duration: 0.9,
      stagger: 0.1,
      ease: 'power3.out',
      scrollTrigger: {
        trigger: secaoProjetos,
        start: 'top 72%',
        once: true,
      },
    });
  }

  if (secaoProjetos && viewport && trilho) {
    const distancia = () => Math.max(0, trilho.scrollWidth - viewport.clientWidth);
    const media = gsap.matchMedia();

    media.add('(min-width: 769px)', () => {
      if (distancia() <= 0) {
        return undefined;
      }

      secaoProjetos.classList.add('has-gsap-horizontal');
      const movimentoHorizontal = gsap.to(trilho, {
        x: () => -distancia(),
        ease: 'none',
        scrollTrigger: {
          trigger: secaoProjetos,
          start: 'top top',
          end: () => `+=${distancia()}`,
          pin: true,
          scrub: movimentoReduzido ? true : 0.75,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onUpdate: ({ progress }) => {
            if (progresso) {
              gsap.set(progresso, { scaleX: progress });
            }
          },
        },
      });

      if (!movimentoReduzido) {
        document.querySelectorAll('[data-project-card]').forEach((cartao) => {
          const imagem = cartao.querySelector('img');
          if (!imagem) {
            return;
          }

          gsap.fromTo(
            imagem,
            { scale: 1.14 },
            {
              scale: 1,
              ease: 'none',
              scrollTrigger: {
                trigger: cartao,
                containerAnimation: movimentoHorizontal,
                start: 'left right',
                end: 'right left',
                scrub: true,
              },
            },
          );
        });
      }

      return () => {
        secaoProjetos.classList.remove('has-gsap-horizontal');
        gsap.set(trilho, { clearProps: 'transform' });
      };
    });

    const atualizarProgressoMovel = () => {
      if (window.innerWidth > 768 || !progresso) {
        return;
      }
      const total = viewport.scrollWidth - viewport.clientWidth;
      gsap.set(progresso, { scaleX: total > 0 ? viewport.scrollLeft / total : 0 });
    };
    viewport.addEventListener('scroll', atualizarProgressoMovel, { passive: true });
  }

  animarCortina('.about-curtain');

  if (!movimentoReduzido) {
    gsap.fromTo(
      '[data-about-marquee]',
      { xPercent: -8 },
      {
        xPercent: -38,
        ease: 'none',
        scrollTrigger: {
          trigger: '.about-section',
          start: 'top bottom',
          end: 'bottom top',
          scrub: 1,
        },
      },
    );
  }

  document.querySelectorAll('[data-section]').forEach((secao) => {
    ScrollTrigger.create({
      trigger: secao,
      start: 'top 55%',
      end: 'bottom 45%',
      onToggle: ({ isActive }) => {
        if (!isActive) {
          return;
        }
        const id = secao.dataset.section;
        document.querySelectorAll('[data-nav-link]').forEach((link) => {
          link.classList.toggle('is-active', link.dataset.navLink === id);
        });
      },
    });
  });
}
