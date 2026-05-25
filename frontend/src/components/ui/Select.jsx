/**
 * Componente de Seleção de Opções (Dropdown/Select).
 * 
 * Um seletor customizável construído sobre o elemento nativo HTML `<select>` contendo
 * estilizações sutis e indicador visual de seta descendente absolutizada.
 *
 * @component
 * @param {Object} props - Propriedades do seletor.
 * @param {string} [props.className] - Estilos CSS extras do Tailwind.
 * @param {React.ReactNode} props.children - As tags `<option>` representando as escolhas da caixa.
 * @param {React.SelectHTMLAttributes<HTMLSelectElement>} props - Atributos HTML `<select>` nativos.
 * @param {React.Ref<HTMLSelectElement>} ref - Referência DOM encaminhada.
 * @returns {React.JSX.Element}
 */
import * as React from "react"
import { cn } from "../../lib/utils"
import { ChevronDown } from "lucide-react"

const Select = React.forwardRef(({ className, children, ...props }, ref) => (
  <div className="relative">
    <select
      ref={ref}
      className={cn(
        "flex h-10 w-full appearance-none rounded-md border border-input bg-background px-3 pr-9 py-2 text-sm text-foreground",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "transition-colors duration-200",
        className
      )}
      {...props}
    >
      {children}
    </select>
    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
  </div>
))
Select.displayName = "Select"

export { Select }
