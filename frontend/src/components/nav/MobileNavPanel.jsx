/**
 * Painel full-screen que desce da navbar abaixo de 1280px.
 *
 * É um DISCLOSURE, não um diálogo. O `guide-modals.md` fundamenta modalidade em
 * "garantir que o usuário perceba que está num sub-estado da aplicação" — e aqui
 * não há sub-estado: o header segue visível e operável (fechar, ajuda, tema).
 * Portanto: sem `role="dialog"`, sem `aria-modal`, sem focus trap. Prender o foco
 * num painel não-modal tornaria ajuda e tema inalcançáveis, e o A11Y.md
 * classifica focus trap vazado como 🔴 CRITICAL.
 *
 * A trava de scroll do corpo (em `useNavMenu`) é medida de reflow (SC 1.4.10),
 * não alegação de modalidade.
 *
 * @module components/nav/MobileNavPanel
 */
import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';
import { NavLinkList } from './NavLinkList';

/**
 * @param {Object} props
 * @param {boolean} props.isOpen - Se o painel está visível.
 * @param {boolean} props.isDesktop - Acima do breakpoint o painel fica inert.
 * @param {Array<Object>} props.groups - Grupos de navegação.
 * @param {string | null} props.openSectionId - Seção expandida (abertura única).
 * @param {(id: string) => void} props.onToggleSection - Alterna uma seção.
 * @param {string | null} props.activePath - Caminho do item de menu ativo.
 * @param {string | null} props.activeGroupId - Grupo da rota atual.
 * @param {(path: string) => void} props.onNavigate - Chamado ao clicar num link.
 * @param {React.ReactNode} props.footer - Bloco de usuário/logout no rodapé.
 * @returns {React.JSX.Element}
 */
export function MobileNavPanel({
  isOpen,
  isDesktop,
  groups,
  openSectionId,
  onToggleSection,
  activePath,
  activeGroupId,
  onNavigate,
  footer,
}) {
  return (
    <div
      id="mobile-nav-panel"
      inert={!isOpen || isDesktop}
      className={cn(
        // `dvh` e não `vh`: o chrome do browser mobile faz `vh` mentir. A 400% de
        // zoom (~320px CSS) isto rola SÓ na vertical.
        'fixed inset-x-0 top-16 z-40 max-h-[calc(100dvh-4rem)] w-full overflow-y-auto',
        'border-b border-border/60 bg-background lg:hidden',
        'motion-safe:transition-transform motion-safe:duration-200',
        isOpen ? 'translate-y-0' : 'pointer-events-none -translate-y-full opacity-0'
      )}
    >
      <nav aria-label="Principal" className="px-4 py-4">
        <ul>
          {groups.map((group) => {
            const expanded = openSectionId === group.id;
            const triggerId = `m-trig-${group.id}`;
            const panelId = `m-panel-${group.id}`;

            return (
              <li key={group.id} className="border-b border-border/50">
                {/* Mesmo contrato de disclosure do desktop. Deliberadamente NÃO é
                    um tablist: sem contrato de setas, sem roving tabindex. */}
                <button
                  type="button"
                  id={triggerId}
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  onClick={() => onToggleSection(group.id)}
                  className={cn(
                    // 48px: afordância primária de navegação numa superfície de toque.
                    'flex min-h-12 w-full items-center justify-between rounded-md px-2 text-left',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    'focus-visible:ring-offset-2',
                    activeGroupId === group.id
                      ? 'font-bold text-foreground'
                      : 'font-medium text-foreground/80'
                  )}
                >
                  <span className="text-base">{group.label}</span>
                  <ChevronDown
                    aria-hidden="true"
                    className={cn(
                      'h-4 w-4 shrink-0 text-muted-foreground',
                      'motion-safe:transition-transform motion-safe:duration-300',
                      expanded && 'rotate-180'
                    )}
                  />
                </button>

                {/* `grid-rows-[1fr]/[0fr]`: a técnica já provada do ui/Accordion.
                    A altura é MEDIDA a partir do conteúdo, então não pode cortar
                    sob line-height 1.5x / letter-spacing 0.12x (SC 1.4.12) — ao
                    contrário do `max-h-[500px]` que a sidebar antiga usava. */}
                <div
                  id={panelId}
                  inert={!expanded}
                  aria-hidden={!expanded}
                  className={cn(
                    'grid overflow-hidden motion-safe:transition-all motion-safe:duration-300',
                    expanded ? 'grid-rows-[1fr] pb-3 opacity-100' : 'grid-rows-[0fr] opacity-0'
                  )}
                >
                  <div className="overflow-hidden px-2">
                    <NavLinkList
                      labelId={`m-lbl-${group.id}`}
                      triggerId={triggerId}
                      label="Ir para"
                      items={group.items}
                      activePath={activePath}
                      onNavigate={onNavigate}
                      size="md"
                    />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-border/50 bg-muted/20 px-4 py-4">{footer}</div>
    </div>
  );
}
