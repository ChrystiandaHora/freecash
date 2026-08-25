/**
 * Coluna de links tipográficos de um painel de navegação.
 *
 * Compartilhado entre o mega-painel (desktop) e o acordeão (mobile) para que o
 * contrato de acessibilidade dos links exista num único lugar.
 *
 * @module components/nav/NavLinkList
 */
import { Link } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { SectionLabel } from '../ui/SectionLabel';

/**
 * @param {Object} props
 * @param {string} props.labelId - Id do rótulo da coluna ("Ir para").
 * @param {string} props.triggerId - Id do gatilho, concatenado ao rótulo no nome acessível.
 * @param {string} props.label - Texto do rótulo da coluna.
 * @param {Array<{name: string, path: string}>} props.items - Links da coluna.
 * @param {string | null} props.activePath - Caminho do item de menu ativo.
 * @param {(path: string) => void} props.onNavigate - Chamado ao clicar num link.
 * @param {'lg' | 'md'} [props.size='lg'] - Escala tipográfica dos links.
 * @returns {React.JSX.Element}
 */
export function NavLinkList({
  labelId,
  triggerId,
  label,
  items,
  activePath,
  onNavigate,
  size = 'lg',
}) {
  return (
    <div>
      {/* Rótulo da coluna é <span>, NÃO heading: cinco painéis transientes
          injetariam cinco entradas homônimas no rotor de headings, que é um mapa
          da estrutura do documento — cromo de navegação não é estrutura. */}
      <SectionLabel as="span" id={labelId} className="mb-3">
        {label}
      </SectionLabel>

      {/* O nome acessível vem de DOIS IDREFs, que concatenam em ordem de DOM →
          "Ir para Financeiro". Sem o id do gatilho seriam cinco listas todas
          chamadas "Ir para", indistinguíveis num rotor de leitor de tela. */}
      <ul aria-labelledby={`${labelId} ${triggerId}`} className="space-y-0.5">
        {items.map((item) => {
          const isActive = activePath === item.path;
          return (
            <li key={item.path}>
              <Link
                to={item.path}
                // WCAG 4.1.2 + é também o gancho de CSS do forced-colors, para o
                // estado visual e o programático não divergirem.
                aria-current={isActive ? 'page' : undefined}
                onClick={() => onNavigate(item.path)}
                className={cn(
                  // `flex` + `min-h-11` faz a LINHA TODA ser o alvo de 44px
                  // (SC 2.5.8, House Rule do A11Y.md). `min-h` e não `h`, para a
                  // letter-spacing de 0.12x não cortar o texto (SC 1.4.12).
                  'flex min-h-11 items-center rounded-md px-3 transition-colors',
                  // ring-offset-card e não o fundo da página: dentro do painel o
                  // offset padrão renderiza um halo de cor errada.
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  'focus-visible:ring-offset-2 focus-visible:ring-offset-card',
                  size === 'lg' ? 'text-lg' : 'text-sm',
                  isActive
                    // Texto ativo é NEUTRO, não a tinta da marca: `text-primary`
                    // (#007acc) daria 3,97:1 sobre o popover escuro e reprovaria
                    // a SC 1.4.3. `text-foreground` dá 16,4:1 no claro e 11,2:1
                    // no escuro. O azul fica no sublinhado, que é elemento
                    // não-textual e precisa de apenas 3:1.
                    //
                    // Peso + sublinhado são os canais redundantes não-cromáticos
                    // exigidos pela SC 1.4.1 — o painel é sem ícones por design,
                    // então a fórmula "Icon + Text + Color" não se aplica aqui.
                    ? 'font-bold text-foreground underline decoration-primary decoration-2 underline-offset-4'
                    // Hover usa tinta de FUNDO, para os dois canais nunca colidirem.
                    : 'font-medium text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {item.name}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
