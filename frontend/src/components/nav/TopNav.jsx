/**
 * Barra de navegação superior com mega-menu (estilo apple.com).
 *
 * Substituiu a sidebar fixa de 288px em todas as larguras. Os cinco grupos ficam
 * na horizontal a partir de 1280px; abaixo disso um painel full-screen desce com
 * as seções em acordeão.
 *
 * PADRÃO: navegação por DISCLOSURE, não `menubar` — ver NavMenuTrigger.jsx.
 *
 * Guardas de anti-padrão do A11Y.md observadas aqui:
 * - Nenhum `<div onClick>`: todo gatilho é `<button type="button">`.
 * - Nenhum focus trap vazado: o painel desktop NÃO é modal e NÃO prende o foco.
 * - Nenhuma referência ARIA órfã: os cinco painéis ficam SEMPRE montados, porque
 *   os gatilhos apontam para eles via `aria-controls`.
 * - Um único landmark `<nav>` por viewport; nenhum `<nav>` aninhado por painel.
 *
 * @module components/nav/TopNav
 */
import { useMemo, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, Wallet, X } from 'lucide-react';
import { navGroups, navIndex } from '../../config/navigation';
import { findActiveNav } from '../../lib/navigation';
import {
  DESKTOP_NAV_QUERY,
  FINE_HOVER_QUERY,
  useMediaQuery,
} from '../../hooks/useMediaQuery';
import { useNavMenu } from './useNavMenu';
import { NavMenuTrigger } from './NavMenuTrigger';
import { MegaPanel } from './MegaPanel';
import { MobileNavPanel } from './MobileNavPanel';
import { UserMenu } from './UserMenu';
import { HelpButton } from './HelpButton';

/**
 * @param {Object} props
 * @param {React.RefObject<HTMLElement>} props.mainRef - Ref do `<main>`, usada na guarda de
 *   SC 2.4.11 e para reposicionar o foco ao clicar na rota já ativa.
 * @returns {React.JSX.Element}
 */
export default function TopNav({ mainRef }) {
  const { pathname } = useLocation();
  const isDesktop = useMediaQuery(DESKTOP_NAV_QUERY);
  const canHover = useMediaQuery(FINE_HOVER_QUERY);

  // Resolve UMA vez por rota, em vez de 18 comparações por render.
  const active = useMemo(() => findActiveNav(pathname, navIndex), [pathname]);
  const activePath = active?.item.path ?? null;
  const activeGroupId = active?.groupId ?? null;

  // Os refs vivem aqui, e nao dentro do useNavMenu: o React Compiler nao consegue
  // provar que `menu.containerRef` e um objeto de ref, e acusa acesso a ref
  // durante a renderizacao.
  const containerRef = useRef(null);
  const triggerRefs = useRef({});
  const panelRefs = useRef({});
  const mobileTriggerRef = useRef(null);
  const accountTriggerRef = useRef(null);
  const accountPanelRef = useRef(null);

  const menu = useNavMenu({
    isDesktop,
    canHover,
    pathname,
    mainRef,
    initialSectionId: activeGroupId ?? 'geral',
    refs: { containerRef, triggerRefs, panelRefs, mobileTriggerRef, accountTriggerRef },
  });

  /**
   * Fecha o painel ao navegar.
   *
   * O fechamento aqui é INCONDICIONAL, e isso é necessário além do efeito de troca
   * de rota: se o link clicado já é a rota atual, `pathname` não muda, o efeito
   * nunca dispara, o painel fica `inert` e o foco cairia no `<body>`. Nesse caso
   * reposicionamos o foco no conteúdo principal — mesma correção que o
   * DashboardLayout já documentava antes do refactor.
   */
  const onNavigate = (path) => {
    menu.closeAll();
    if (menu.isMobileOpen) menu.closeMobile();
    if (path === pathname) mainRef?.current?.focus();
  };

  /**
   * Setas como conveniência PURAMENTE ADITIVA: todo gatilho e link mantém o
   * `tabindex="0"` natural, e as setas só chamam `.focus()` no vizinho. O APG
   * marca estas linhas como "(Optional)"; roving tabindex tiraria 21 de 23
   * controles da ordem de tabulação e quebraria a expectativa de quem tabula.
   *
   * Sem wrapping nas pontas — wrapping é afordância de menu, não de disclosure.
   */
  const onTriggerKeyDown = (groupId, index) => (event) => {
    const ids = navGroups.map((g) => g.id);

    const focusTrigger = (i) => {
      const target = triggerRefs.current[ids[i]];
      if (!target) return;
      event.preventDefault();
      menu.withFocusSuppressed(() => target.focus());
    };

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (menu.openId === groupId) {
          panelRefs.current[groupId]?.querySelector('a[href]')?.focus();
        } else {
          menu.openPanel(groupId);
        }
        break;
      case 'ArrowUp':
        if (menu.openId === groupId) {
          event.preventDefault();
          menu.closeAll();
        }
        break;
      case 'ArrowRight':
        if (index < ids.length - 1) focusTrigger(index + 1);
        break;
      case 'ArrowLeft':
        if (index > 0) focusTrigger(index - 1);
        break;
      default:
        break;
    }
  };

  /** Fecha quando o Tab sai do último link do painel. */
  const onSectionBlur = (groupId) => (event) => {
    if (event.currentTarget.contains(event.relatedTarget)) return;
    if (menu.openId === groupId) menu.closeAll();
  };

  const isPanelOpen = Boolean(menu.openId) && isDesktop;

  return (
    <>
      {/* Scrim. Copia o contrato do backdrop do ui/Modal: aria-hidden, sem role,
          sem nome e sem tabindex — seu equivalente de teclado é o Escape, e é
          isso que satisfaz a SC 2.1.1. Um `role="button"` aqui criaria um botão
          sem nome acessível (falha 4.1.2).

          `bg-black/40` é o TETO nos dois temas: em /45 o texto do conteúdo atrás
          cai para 4,02:1 no escuro e reprova a SC 1.4.3. Como este painel NÃO é
          `aria-modal`, o conteúdo atrás continua na árvore de TA e legível, então
          o contraste dele ainda conta — diferente do ui/Modal, que pode usar /60
          justamente porque remove o fundo da árvore. */}
      {isPanelOpen && (
        <div
          aria-hidden="true"
          onClick={() => menu.closeAll()}
          className="nav-scrim fixed inset-x-0 bottom-0 top-16 z-30 bg-black/40 backdrop-blur-sm motion-safe:transition-opacity forced-colors:hidden"
        />
      )}

      {/* `sticky` só a partir de xl: a 400% de zoom uma barra de 64px consumiria
          ~20% da altura útil da viewport (SC 1.4.10).
          `relative` é o ancestral posicionado que os painéis full-width resolvem.
          O glass vive no <div> interno, NÃO no <header>: `backdrop-filter` torna o
          elemento containing block de descendentes `position: fixed`, e um scrim
          `fixed inset-0` aqui dentro se dimensionaria pela caixa de 64px. */}
      <header
        ref={containerRef}
        onMouseLeave={menu.scheduleClose}
        className="relative z-40 lg:sticky lg:top-0"
      >
        <div className="flex h-16 items-center justify-between border-b border-border/50 bg-card/80 px-4 backdrop-blur-md sm:px-6 xl:px-8">
          <div className="mx-auto flex h-full w-full max-w-[1600px] items-center justify-between gap-4">
            <div className="flex h-full items-center gap-6">
              {/* Gatilho mobile: 48x48, afordância primária numa superfície de toque. */}
              <button
                type="button"
                ref={mobileTriggerRef}
                onClick={menu.toggleMobile}
                aria-expanded={menu.isMobileOpen}
                aria-controls="mobile-nav-panel"
                aria-label={menu.isMobileOpen ? 'Fechar menu' : 'Abrir menu'}
                className="inline-flex h-12 w-12 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 lg:hidden"
              >
                {menu.isMobileOpen ? (
                  <X className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <Menu className="h-5 w-5" aria-hidden="true" />
                )}
              </button>

              <Link
                to="/dashboard"
                onClick={() => onNavigate('/dashboard')}
                className="flex shrink-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary shadow-lg shadow-primary/20">
                  <Wallet className="h-5 w-5 text-primary-foreground" aria-hidden="true" />
                </span>
                {/* Abaixo de `xl` o ícone carrega a marca sozinho: são os ~98px que fazem
                      os cinco gatilhos caberem a partir de 1024px. */}
                <span className="hidden text-xl font-bold tracking-tight text-primary xl:inline">
                  FreeCash
                </span>
              </Link>

              {/* UM landmark para a barra inteira. Rótulo "Principal" e não
                  "Navegação principal": o nome do papel já é falado, então o
                  segundo saía como "Navegação principal, navegação". */}
              <nav aria-label="Principal" className="hidden h-full lg:block">
                <ul className="flex h-full items-stretch gap-1">
                  {navGroups.map((group, index) => {
                    const triggerId = `navtrig-${group.id}`;
                    const panelId = `navpanel-${group.id}`;
                    const isOpen = menu.openId === group.id;

                    return (
                      // O painel é irmão de DOM do gatilho, dentro do mesmo <li>.
                      // É isso que faz Tab/Shift+Tab fluírem do gatilho para os
                      // links e de volta, sem uma linha de JS — e é por isso que
                      // ele NÃO pode ser portalado para document.body.
                      <li
                        key={group.id}
                        className="flex items-center"
                        onBlur={onSectionBlur(group.id)}
                      >
                        <NavMenuTrigger
                          group={group}
                          isOpen={isOpen}
                          isActive={activeGroupId === group.id}
                          triggerId={triggerId}
                          panelId={panelId}
                          onToggle={() => menu.togglePanel(group.id)}
                          onPointerEnter={menu.onTriggerPointerEnter(group.id)}
                          onPointerLeave={menu.scheduleClose}
                          onFocus={menu.onTriggerFocus(group.id)}
                          onKeyDown={onTriggerKeyDown(group.id, index)}
                          triggerRef={(el) => (triggerRefs.current[group.id] = el)}
                        />
                        <MegaPanel
                          group={group}
                          isOpen={isOpen}
                          panelId={panelId}
                          triggerId={triggerId}
                          activePath={activePath}
                          onNavigate={onNavigate}
                          onPointerEnter={menu.cancelClose}
                          onPointerLeave={menu.scheduleClose}
                          panelRef={(el) => (panelRefs.current[group.id] = el)}
                        />
                      </li>
                    );
                  })}
                </ul>
              </nav>
            </div>

            {/* Ordem fixa em TODOS os breakpoints: ajuda → tema → (divisor) → sair.
                SC 3.2.6 Consistent Help permite reflow, não reordenação — a ajuda
                nunca muda de posição relativa, e é por isso que ela vem primeiro.

                Só a ajuda fica solta na barra, porque a SC 3.2.6 Consistent Help
                exige que o ponto de entrada de ajuda viva no layout compartilhado e
                não mude de ordem relativa entre breakpoints.

                Tudo que é "meu" — identidade, tema e sair — está atrás do avatar.
                Relógio e nome escrito saíram de vez: num header cuja função é
                navegar, os dois eram ruído. O divisor separa a ajuda da área de
                conta. */}
            <div className="flex shrink-0 items-center gap-2">
              <HelpButton />
              <div className="mx-1 hidden h-5 w-px bg-border lg:block" aria-hidden="true" />
              <div className="hidden lg:block">
                <UserMenu
                  isOpen={menu.isAccountOpen}
                  onToggle={menu.toggleAccount}
                  onClose={menu.closeAccount}
                  triggerRef={accountTriggerRef}
                  panelRef={accountPanelRef}
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      <MobileNavPanel
        isOpen={menu.isMobileOpen}
        isDesktop={isDesktop}
        groups={navGroups}
        openSectionId={menu.openSectionId}
        onToggleSection={menu.toggleSection}
        activePath={activePath}
        activeGroupId={activeGroupId}
        onNavigate={onNavigate}
        footer={<UserMenu variant="stacked" />}
      />
    </>
  );
}
