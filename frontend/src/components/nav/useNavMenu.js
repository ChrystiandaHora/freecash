/**
 * Hook de controle de estado do menu de navegação (TopNav).
 * Gerencia abertura/fechamento, delays de hover/focus e descarte acessível (Escape/clique fora).
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const OPEN_DELAY_MS = 120;
const CLOSE_DELAY_MS = 300;

const isModalOpen = () => !!document.querySelector('[role="dialog"][aria-modal="true"]');

/**
 * @param {Object} params
 * @param {boolean} params.isDesktop
 * @param {boolean} params.canHover
 * @param {string} params.pathname
 * @param {React.RefObject<HTMLElement>} params.mainRef
 * @param {string | null} params.initialSectionId
 * @param {Object} params.refs
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
  const openIdRef = useRef(null);
  const suppressFocusOpen = useRef(false);
  const lastInput = useRef('pointer');

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
      setAccountOpen(false); // Exclusividade mútua com menu de conta
    },
    [clearTimers]
  );

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
      const active = document.activeElement;
      // Não fecha se o foco ainda estiver dentro do painel ou no gatilho
      if (panelRefs.current[current]?.contains(active)) return;
      if (triggerRefs.current[current] === active) return;
      closeAll();
    }, CLOSE_DELAY_MS);
  }, [clearTimers, closeAll, panelRefs, triggerRefs]);

  const onTriggerPointerEnter = useCallback(
    (id) => () => {
      if (!isDesktop || !canHover || isModalOpen()) return;

      // Não sobrepõe com hover quando o usuário estiver navegando por teclado no conteúdo
      const active = document.activeElement;
      if (
        lastInput.current === 'keyboard' &&
        active !== mainRef?.current &&
        mainRef?.current?.contains(active)
      ) {
        return;
      }

      clearTimers();
      // Troca instantânea entre itens vizinhos quando um painel já está aberto
      openTimer.current = setTimeout(() => openPanel(id), openIdRef.current ? 0 : OPEN_DELAY_MS);
    },
    [isDesktop, canHover, mainRef, clearTimers, openPanel]
  );

  const onTriggerFocus = useCallback(
    (id) => (event) => {
      if (suppressFocusOpen.current) return;
      if (!event.target.matches(':focus-visible')) return;
      openPanel(id);
    },
    [openPanel]
  );

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
        setOpenId(null);
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

  // Escape: descarta menus abertos restaurando o foco adequadamente
  useEffect(() => {
    if (!openId && !isMobileOpen && !isAccountOpen) return;

    const onKey = (event) => {
      if (event.key !== 'Escape') return;
      if (document.activeElement?.closest('[role="dialog"][aria-modal="true"]')) return;

      if (isMobileOpen) {
        event.stopPropagation();
        setMobileOpen(false);
        mobileTriggerRef.current?.focus();
        return;
      }

      if (isAccountOpen) {
        event.stopPropagation();
        closeAccount({ restoreFocus: true });
        return;
      }

      const panel = panelRefs.current[openId];
      const trigger = triggerRefs.current[openId];
      const active = document.activeElement;

      if (panel?.contains(active)) {
        event.stopPropagation();
        closeAll({ restoreFocus: true, id: openId });
      } else if (active === trigger) {
        event.stopPropagation();
        closeAll();
      } else {
        closeAll({ restoreFocus: false });
      }
    };

    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [openId, isMobileOpen, isAccountOpen, closeAll, closeAccount, panelRefs, triggerRefs, mobileTriggerRef]);

  // Fecha menus ao clicar fora do container do TopNav
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

  // Reseta menus ao navegar ou alternar entre desktop e mobile
  const routeKey = `${pathname}|${isDesktop}`;
  const [lastRouteKey, setLastRouteKey] = useState(routeKey);
  if (lastRouteKey !== routeKey) {
    setLastRouteKey(routeKey);
    setOpenId(null);
    setMobileOpen(false);
    setAccountOpen(false);
  }

  useEffect(() => {
    if (openId === null && !isMobileOpen) clearTimers();
  }, [openId, isMobileOpen, clearTimers]);

  // Trava scroll de fundo quando o drawer mobile está aberto
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
