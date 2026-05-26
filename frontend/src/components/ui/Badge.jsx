/**
 * Componente de Emblema (Badge) Informativo.
 * 
 * Exibe pequenos status, categorias ou tags estilizados com cores harmônicas
 * translúcidas e bordas sutis.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS extras do Tailwind.
 * @param {"default" | "destructive" | "warning" | "success" | "secondary" | "outline"} [props.variant="default"] - Estilo temático do status exibido.
 * @param {React.HTMLAttributes<HTMLSpanElement>} props - Demais atributos de elemento HTML `<span>`.
 * @param {React.Ref<HTMLSpanElement>} ref - Referência DOM encaminhada.
 * @returns {React.JSX.Element} Elemento JSX do Badge renderizado.
 */
import * as React from "react"
import { cn } from "../../lib/utils"

const variantStyles = {
  default: "bg-primary/10 text-primary border border-primary/20",
  destructive: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
  warning: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/20",
  success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
  secondary: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-200/50 dark:border-slate-700/50",
  outline: "border border-border text-foreground",
}

const Badge = React.forwardRef(({ className, variant = "default", ...props }, ref) => (
  <span
    ref={ref}
    className={cn(
      "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
      variantStyles[variant],
      className
    )}
    {...props}
  />
))
Badge.displayName = "Badge"

export { Badge }
