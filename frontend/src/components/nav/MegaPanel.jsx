/**
 * Painel full-width que desce da navbar (desktop).
 *
 * Puramente tipográfico: não lê `item.icon`, por decisão de design.
 *
 * Quatro detalhes estruturais sustentam a acessibilidade: é irmão de DOM do seu gatilho,
 * dentro do mesmo `<li>`, e **não** pode ser portalado — é a ordem do DOM que faz
 * Tab/Shift+Tab fluírem entre gatilho e links sem uma linha de JS; recebe `inert` quando
 * fechado, saindo da ordem de foco; fica sempre montado, porque `aria-controls` aponta
 * para ele e o A11Y.md proíbe referência ARIA órfã; e a altura é dirigida pelo conteúdo,
 * com teto em viewport — um `max-h` fixo cortaria links sob letter-spacing (SC 1.4.12).
 */
import { cn } from '../../lib/utils';
import { NavLinkList } from './NavLinkList';

/**
 * @param {Object} props
 * @param {{id: string, label: string, items: Array<Object>}} props.group - Grupo renderizado.
 * @param {boolean} props.isOpen - Se este painel está aberto.
 * @param {string} props.panelId - Id casado com o `aria-controls` do gatilho.
 * @param {string} props.triggerId - Id do gatilho.
 * @param {string | null} props.activePath - Caminho do item de menu ativo.
 * @param {(path: string) => void} props.onNavigate - Chamado ao clicar num link.
 * @param {() => void} props.onPointerEnter - Cancela o fechamento agendado (SC 1.4.13 "hoverable").
 * @param {() => void} props.onPointerLeave - Agenda o fechamento.
 * @param {(el: HTMLElement | null) => void} props.panelRef - Callback ref.
 */
export function MegaPanel({
  group,
  isOpen,
  panelId,
  triggerId,
  activePath,
  onNavigate,
  onPointerEnter,
  onPointerLeave,
  panelRef,
}) {
  return (
    <div
      id={panelId}
      ref={panelRef}
      inert={!isOpen}
      // SC 1.4.13 "hoverable": o painel NÃO pode desaparecer quando o ponteiro
      // entra nele. Não-negociável.
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
      className={cn(
        'nav-panel absolute inset-x-0 top-full origin-top overflow-y-auto',
        'max-h-[min(70vh,32rem)] border-b border-border/60 bg-popover',
        'text-popover-foreground shadow-lg',
        'motion-safe:transition-[opacity,transform] motion-safe:duration-200 motion-safe:ease-out',
        isOpen
          ? 'pointer-events-auto translate-y-0 opacity-100'
          : 'pointer-events-none -translate-y-1 opacity-0'
      )}
    >
      <div className="mx-auto grid max-w-[1600px] gap-10 px-6 py-10 sm:grid-cols-2 lg:px-8">
        <NavLinkList
          labelId={`navlbl-${group.id}`}
          triggerId={triggerId}
          label="Ir para"
          items={group.items}
          activePath={activePath}
          onNavigate={onNavigate}
        />
      </div>
    </div>
  );
}
