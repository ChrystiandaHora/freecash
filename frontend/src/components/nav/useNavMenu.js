/**
 * Máquina de estado do mega-menu da navbar.
 *
 * Concentra abertura/fechamento, intenção de hover e as cinco vias de fechamento. Vive
 * como estado local do TopNav: nada fora da subárvore dele precisa saber que um painel
 * está aberto.
 *
 * Contrato da SC 1.4.13 (A11Y.md / WCAG 2.2 AA): *hoverable* — o painel não fecha quando
 * o ponteiro entra nele, daí o `cancelClose` no `onPointerEnter`; *persistent* — sem
 * auto-fechamento por ociosidade, embora fechar quando o gatilho perde hover/foco seja
 * condição permitida; *dismissible* — Escape descarta sem mover o foco quando ele está
 * fora do painel. Por SC 2.1.1, clique, Enter, Espaço e foco abrem com atraso zero; só o
 * hover é debounced.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/** Filtro de intenção: uma varredura de ponteiro pela barra não abre nada. */
const OPEN_DELAY_MS = 120;
/** Paga o trajeto diagonal do gatilho até o painel (forma prática do "hoverable"). */
const CLOSE_DELAY_MS = 300;

const isModalOpen = () => !!document.querySelector('[role="dialog"][aria-modal="true"]');

/**
 * @param {Object} params
 * @param {boolean} params.isDesktop - Se a navbar horizontal está ativa.
 * @param {boolean} params.canHover - Se o ponteiro tem hover real (mouse/trackpad).
 * @param {string} params.pathname - `location.pathname` atual.
 * @param {React.RefObject<HTMLElement>} params.mainRef - Ref do `<main>`, para a guarda de SC 2.4.11.
 * @param {string | null} params.initialSectionId - Seção aberta por padrão no acordeão mobile.
 * @param {Object} params.refs - Refs criados pelo componente (o React Compiler não
 *   enxerga refs devolvidos dentro do objeto de retorno de um hook customizado).
 */
export function useNavMenu({
  isDesktop,
  canHover,
  pathname,
  mainRef,
  initialSectionId,
  refs: { containerRef, triggerRefs, panelRefs, mobileTriggerRef, accountTriggerRef },
}) {
  const [openId, setOpenId] = useState(null);
  const [isMobileOpen, setMobileOpen] = useState(false);
  const [openSectionId, setOpenSectionId] = useState(initialSectionId ?? null);
  const [isAccountOpen, setAccountOpen] = useState(false);

  const openTimer = useRef(null);
  const closeTimer = useRef(null);
  // Espelha `openId` para os callbacks de timer lerem valor fresco sem entrar
  // nas dependências (e sem re-armar o timer a cada render).
  const openIdRef = useRef(null);
  // Evita que o `onFocus` reabra o painel que Escape ou Shift+Tab acabou de deixar.
  const suppressFocusOpen = useRef(false);
  // Última modalidade de entrada, para a guarda de SC 2.4.11.
  const lastInput = useRef('pointer');


  // Espelha o estado num efeito, nao durante a renderizacao: os callbacks de
  // timer disparam depois do commit, entao sempre leem valor fresco.
  useEffect(() => {
    openIdRef.current = openId;
  }, [openId]);

  const clearTimers = useCallback(() => {
    clearTimeout(openTimer.current);
    clearTimeout(closeTimer.current);
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  useEffect(() => {
    const onKeyDown = () => (lastInput.current = 'keyboard');
    const onPointerDown = () => (lastInput.current = 'pointer');
    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('pointerdown', onPointerDown, true);
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('pointerdown', onPointerDown, true);
    };
  }, []);

  const openPanel = useCallback(
    (id) => {
      clearTimers();
      setOpenId(id);
      // Exclusividade mútua: painel de navegação e menu de conta nunca coexistem.
      // Eles se sobreporiam visualmente, e ter dois popups abertos deixa ambíguo
      // o que o Escape deve fechar.
      setAccountOpen(false);
    },
    [clearTimers]
  );

  /**
   * Fecha o painel. `restoreFocus` é OPT-IN de propósito: devolver o foco ao
   * gatilho de forma incondicional dispararia a cada mouse-out, o que seria uma
   * mudança espontânea de contexto (WCAG 2.4.3).
   */
  const closeAll = useCallback(
    ({ restoreFocus = false, id } = {}) => {
      clearTimers();
      const target = id ?? openIdRef.current;
      setOpenId(null);
      if (restoreFocus && target) {
        suppressFocusOpen.current = true;
        triggerRefs.current[target]?.focus();
        requestAnimationFrame(() => {
          suppressFocusOpen.current = false;
        });
      }
    },
    [clearTimers, triggerRefs]
  );

  const togglePanel = useCallback(
    (id) => (openIdRef.current === id ? closeAll() : openPanel(id)),
    [closeAll, openPanel]
  );

  const cancelClose = useCallback(() => clearTimeout(closeTimer.current), []);

  const scheduleClose = useCallback(() => {
    clearTimers();
    closeTimer.current = setTimeout(() => {
      const current = openIdRef.current;
      if (!current) return;
      // Nunca fecha sob um usuário de teclado cujo foco vive lá dentro: com lupa,
      // é normal ter o foco no painel e o ponteiro em outro lugar da tela.
      const active = document.activeElement;
      if (panelRefs.current[current]?.contains(active)) return;
      if (triggerRefs.current[current] === active) return;
      closeAll();
    }, CLOSE_DELAY_MS);
  }, [clearTimers, closeAll, panelRefs, triggerRefs]);

  const onTriggerPointerEnter = useCallback(
    (id) => () => {
      if (!isDesktop || !canHover || isModalOpen()) return;

      // Guarda de SC 2.4.11 ("focus never entirely obscured by author content"):
      // não deixa o hover cobrir o anel de foco de um usuário de teclado.
      //
      // O `<main>` é EXCLUÍDO da checagem de propósito. O efeito de troca de rota
      // foca o próprio `<main tabIndex={-1}>`, e `node.contains(node)` é `true`;
      // como `lastInput` só muda em pointerdown (não em pointermove), incluir o
      // `<main>` deixaria o hover-open silenciosamente morto após qualquer
      // navegação por teclado. E o `<main>` tem `focus:outline-none`, ou seja não
      // há anel de foco ali para proteger.
      const active = document.activeElement;
      if (
        lastInput.current === 'keyboard' &&
        active !== mainRef?.current &&
        mainRef?.current?.contains(active)
      ) {
        return;
      }

      clearTimers();
      // 0ms quando a barra já está "armada": trocar entre gatilhos vizinhos tem
      // de ser instantâneo, como numa barra de menus.
      openTimer.current = setTimeout(() => openPanel(id), openIdRef.current ? 0 : OPEN_DELAY_MS);
    },
    [isDesktop, canHover, mainRef, clearTimers, openPanel]
  );

  /** SC 1.4.13: "MUST appear on both hover and keyboard focus". */
  const onTriggerFocus = useCallback(
    (id) => (event) => {
      if (suppressFocusOpen.current) return;
      // Foco vindo de pointerdown já é tratado pelo onClick; abrir aqui também
      // faria o clique abrir-e-fechar.
      if (!event.target.matches(':focus-visible')) return;
      openPanel(id);
    },
    [openPanel]
  );

  /** Marca o gatilho para não reabrir no foco que Shift+Tab/setas acabam de dar. */
  const withFocusSuppressed = useCallback((fn) => {
    suppressFocusOpen.current = true;
    fn();
    requestAnimationFrame(() => {
      suppressFocusOpen.current = false;
    });
  }, []);

  const toggleAccount = useCallback(() => {
    setAccountOpen((open) => {
      if (!open) {
        clearTimers();
        setOpenId(null); // ver nota de exclusividade em `openPanel`
      }
      return !open;
    });
  }, [clearTimers]);

  const closeAccount = useCallback(({ restoreFocus = false } = {}) => {
    setAccountOpen(false);
    if (restoreFocus) {
      suppressFocusOpen.current = true;
      accountTriggerRef.current?.focus();
      requestAnimationFrame(() => {
        suppressFocusOpen.current = false;
      });
    }
  }, [accountTriggerRef]);

  // Escape — três ramos. O APG manda mover o foco ao gatilho; a SC 1.4.13 manda
  // descartar "without moving focus". Não se contradizem: falam de locais de foco
  // diferentes.
  useEffect(() => {
    if (!openId && !isMobileOpen && !isAccountOpen) return;

    const onKey = (event) => {
      if (event.key !== 'Escape') return;
      // Cede a vez a um modal aberto: o Modal.jsx também escuta keydown no
      // document, e sem isto um Escape fecharia os dois.
      if (document.activeElement?.closest('[role="dialog"][aria-modal="true"]')) return;

      if (isMobileOpen) {
        event.stopPropagation();
        setMobileOpen(false);
        mobileTriggerRef.current?.focus();
        return;
      }

      // Menu de conta: é um popup de AÇÃO, não de navegação. Aqui o foco sempre
      // volta ao gatilho — ao contrário dos painéis de navegação, ele nunca é
      // aberto por hover, então nunca existe o caso "aberto sem o usuário pedir"
      // que obrigaria a descartar sem mover o foco (SC 1.4.13).
      if (isAccountOpen) {
        event.stopPropagation();
        closeAccount({ restoreFocus: true });
        return;
      }

      const panel = panelRefs.current[openId];
      const trigger = triggerRefs.current[openId];
      const active = document.activeElement;

      if (panel?.contains(active)) {
        // (1) Foco DENTRO do painel: mover é obrigatório — quando o painel fica
        //     `inert`, o foco interno é destruído e cairia no <body>, um beco sem
        //     saída de teclado.
        event.stopPropagation();
        closeAll({ restoreFocus: true, id: openId });
      } else if (active === trigger) {
        // (2) Aberto por teclado, foco no gatilho: fecha e o foco fica.
        event.stopPropagation();
        closeAll();
      } else {
        // (3) Aberto por HOVER, foco em outro lugar: descarta SEM tocar no foco.
        closeAll({ restoreFocus: false });
      }
    };

    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [openId, isMobileOpen, isAccountOpen, closeAll, closeAccount, panelRefs, triggerRefs, mobileTriggerRef]);

  // Clique fora. `pointerdown` e não `click`, para fechar ANTES que o elemento
  // sob o scrim receba qualquer coisa.
  useEffect(() => {
    if (!openId && !isMobileOpen && !isAccountOpen) return;
    const onPointerDown = (event) => {
      if (containerRef.current?.contains(event.target)) return;
      closeAll();
      setMobileOpen(false);
      setAccountOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [openId, isMobileOpen, isAccountOpen, closeAll, containerRef]);

  // Fecha tudo em troca de rota E em cruzamento de breakpoint.
  //
  // Troca de rota é rede de segurança para voltar/avançar do browser e navegação
  // programática — o clique em link fecha por conta própria (ver `onNavigate` no
  // TopNav), porque clicar na rota atual não muda o `pathname`.
  //
  // Breakpoint precisa dos DOIS sentidos: um painel desktop aberto ao encolher a
  // janela ficaria pendurado (a versão anterior, na sidebar, só tratava
  // mobile → desktop).
  //
  // Ajuste de estado durante a renderização, não num efeito: é o padrão que o
  // React recomenda para "resetar estado quando uma entrada muda", e evita o
  // render em cascata que um `setState` dentro de efeito provoca.
  const routeKey = `${pathname}|${isDesktop}`;
  const [lastRouteKey, setLastRouteKey] = useState(routeKey);
  if (lastRouteKey !== routeKey) {
    setLastRouteKey(routeKey);
    setOpenId(null);
    setMobileOpen(false);
    setAccountOpen(false);
  }

  // Com nada aberto, nenhum timer pendente deve sobreviver — senão um hover
  // iniciado antes da navegação reabriria o painel depois dela.
  useEffect(() => {
    if (openId === null && !isMobileOpen) clearTimers();
  }, [openId, isMobileOpen, clearTimers]);

  // Trava o scroll do corpo com o painel mobile aberto. É medida de reflow
  // (SC 1.4.10), não alegação de modalidade — o painel NÃO é um diálogo.
  useEffect(() => {
    if (!isMobileOpen) return;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileOpen]);

  const openMobile = useCallback(() => setMobileOpen(true), []);
  const closeMobile = useCallback(() => {
    setMobileOpen(false);
    mobileTriggerRef.current?.focus();
  }, [mobileTriggerRef]);
  const toggleMobile = useCallback(() => setMobileOpen((v) => !v), []);
  const toggleSection = useCallback(
    (id) => setOpenSectionId((current) => (current === id ? null : id)),
    []
  );

  return {
    openId,
    isMobileOpen,
    isAccountOpen,
    openSectionId,
    openPanel,
    closeAll,
    togglePanel,
    cancelClose,
    scheduleClose,
    onTriggerPointerEnter,
    onTriggerFocus,
    withFocusSuppressed,
    openMobile,
    closeMobile,
    toggleMobile,
    toggleSection,
    toggleAccount,
    closeAccount,
  };
}
