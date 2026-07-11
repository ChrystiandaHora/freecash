/**
 * Rótulo de cabeçalho de seção com ícone.
 *
 * Padroniza o cabeçalho pequeno em uppercase usado para introduzir blocos/cards
 * informativos em toda a aplicação (ex: "Garantia de Privacidade", "Vencimentos").
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {React.ComponentType} [props.icon] - Componente de ícone (lucide-react) exibido à esquerda.
 * @param {string} [props.iconClassName] - Sobrescreve a cor do ícone (default: text-primary). Use para ícones com cor semântica própria (ex: receita/despesa).
 * @param {string} [props.className] - Estilos CSS extras do Tailwind.
 * @param {React.ReactNode} props.children - Texto do rótulo.
 * @returns {React.JSX.Element} Elemento JSX do SectionLabel renderizado.
 *
 * Nota de acessibilidade: usa o token `text-muted-foreground` (não um cinza
 * hardcoded) porque ele já é calibrado para manter contraste >= 4.5:1 (WCAG AA)
 * contra os fundos `--background`/`--card` do tema, em ambos os modos.
 */
import { cn } from "../../lib/utils"

export function SectionLabel({ icon: Icon, iconClassName, className, children, as: Component = "h3", ...props }) {
  return (
    <Component
      className={cn(
        "text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5",
        className
      )}
      {...props}
    >
      {Icon && <Icon className={cn("h-4 w-4 text-primary", iconClassName)} />}
      {children}
    </Component>
  )
}
