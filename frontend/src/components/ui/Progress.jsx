/**
 * Componente de Barra de Progresso Visual (Progress Bar).
 * 
 * Exibe visualmente percentuais de preenchimento de metas de alocação de carteiras
 * ou taxas de poupança, suportando cores temáticas de sucesso, alerta e erro.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Classes CSS extras do Tailwind.
 * @param {number} [props.value=0] - O valor de progresso atual obtido.
 * @param {number} [props.max=100] - O valor total correspondente a 100% de progresso.
 * @param {"default" | "success" | "warning" | "destructive"} [props.variant="default"] - A variante de cor da barra interna.
 * @param {React.HTMLAttributes<HTMLDivElement>} props - Atributos HTML `<div>` nativos.
 * @param {React.Ref<HTMLDivElement>} ref - Referência DOM encaminhada.
 * @returns {React.JSX.Element}
 */
import * as React from "react"
import { cn } from "../../lib/utils"

const Progress = React.forwardRef(({ className, value = 0, max = 100, variant = "default", ...props }, ref) => {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  const trackStyles = "bg-secondary"
  const barVariants = {
    default: "bg-primary",
    success: "bg-emerald-500",
    warning: "bg-orange-500",
    destructive: "bg-red-500",
  }

  return (
    <div
      ref={ref}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className={cn(
        "relative h-2.5 w-full overflow-hidden rounded-full",
        trackStyles,
        className
      )}
      {...props}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 ease-out",
          barVariants[variant] || barVariants.default
        )}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
})
Progress.displayName = "Progress"

export { Progress }
