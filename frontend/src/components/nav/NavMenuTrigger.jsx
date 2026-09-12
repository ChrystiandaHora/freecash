/**
 * Gatilho de primeiro nível da navbar (um por grupo).
 *
 * É um DISCLOSURE, não um `menuitem`: o APG é explícito que navegação de site não usa o
 * papel `menu`, porque não oferece a funcionalidade complexa que a tecnologia assistiva
 * espera dele. Daí as ausências deliberadas:
 *
 * - sem `role="menubar"/"menuitem"`, para os destinos preservarem o papel `link` — é o
 *   que mantém "abrir em nova aba" e o rotor de links funcionando;
 * - sem `aria-haspopup`, que declara menu/listbox/dialog/tree, e disclosure não é nenhum;
 * - sem roving `tabindex`, que tiraria 21 dos 23 controles da ordem de tabulação;
 * - sem `aria-label`: o texto visível é o nome acessível (SC 2.5.3), para comando de voz;
 * - sem `title`: tooltip nativo não é descartável nem hoverable, e falha a SC 1.4.13.
 */
import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * @param {Object} props
 * @param {{id: string, label: string}} props.group - Grupo controlado.
 * @param {boolean} props.isOpen - Se o painel deste grupo está visível.
 * @param {boolean} props.isActive - Se a rota atual pertence a este grupo.
 * @param {string} props.triggerId - Id do botão.
 * @param {string} props.panelId - Id do painel controlado.
 * @param {() => void} props.onToggle - Clique.
 * @param {(event: React.PointerEvent) => void} props.onPointerEnter - Abertura por hover.
 * @param {(event: React.PointerEvent) => void} props.onPointerLeave - Agenda fechamento.
 * @param {(event: React.FocusEvent) => void} props.onFocus - Abertura por foco de teclado.
 * @param {(event: React.KeyboardEvent) => void} props.onKeyDown - Setas.
 * @param {(el: HTMLButtonElement | null) => void} props.triggerRef - Callback ref.
 */
export function NavMenuTrigger({
  group,
  isOpen,
  isActive,
  triggerId,
  panelId,
  onToggle,
  onPointerEnter,
  onPointerLeave,
  onFocus,
  onKeyDown,
  triggerRef,
}) {
  return (
    <button
      // `type="button"` é obrigatório: um <button> sem type dentro de qualquer
      // <form> ancestral submete o formulário.
      type="button"
      id={triggerId}
      ref={triggerRef}
      // Reflete a VISIBILIDADE do painel, não a intenção do usuário — inclusive
      // quando aberto por hover. Painel visível com aria-expanded="false" é
      // mentira para a tecnologia assistiva.
      aria-expanded={isOpen}
      aria-controls={panelId}
      data-active={isActive || undefined}
      onClick={onToggle}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
      onFocus={onFocus}
      onKeyDown={onKeyDown}
      className={cn(
        // min-h-11 = 44px (SC 2.5.8, House Rule do A11Y.md acima do piso AA de 24px).
        // px-3 abaixo de xl faz os 5 gatilhos caberem a partir de 1024px;
        // min-h-11 = 44px (SC 2.5.8) é preservado em toda largura.
        'nav-trigger relative inline-flex min-h-11 items-center gap-1 rounded-md px-3 text-sm xl:px-4',
        'transition-colors focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card',
        isActive
          // SC 1.4.1: peso da fonte + barra de 3px carregam o estado; a cor só
          // reforça. É o análogo horizontal do `border-l-2` que a sidebar usava.
          //
          // `after:content-[""]` é VAZIO de propósito: JAWS e TalkBack anunciam
          // conteúdo gerado por CSS, então um caractere real ("•", "▸") injetaria
          // lixo no nome acessível e arriscaria a SC 2.5.3.
          ? 'font-bold text-foreground after:absolute after:inset-x-3 after:bottom-0 after:h-[3px] after:bg-primary after:content-[""]'
          : 'font-medium text-muted-foreground hover:text-foreground'
      )}
    >
      {group.label}
      <ChevronDown
        aria-hidden="true"
        className={cn(
          'h-3.5 w-3.5 shrink-0 motion-safe:transition-transform motion-safe:duration-200',
          isOpen && 'rotate-180'
        )}
      />
    </button>
  );
}
