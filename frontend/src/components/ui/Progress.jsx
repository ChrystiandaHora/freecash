/**
 * Componente de Barra de Progresso Acessível.
 *
 * Expõe `role="progressbar"` com `aria-valuenow/min/max` e nome acessível obrigatório, e
 * renderiza o percentual como texto (WCAG 1.4.1 — estado nunca só por cor). A barra
 * visual para em 100%, mas `aria-valuenow` reporta o valor real: uma meta de teto
 * estourada precisa ser anunciada como tal.
 *
 * @param {number} props.value - Valor atual do progresso.
 * @param {number} [props.max=100] - Valor que representa 100%.
 * @param {string} props.label - Nome acessível (ex.: "Reserva de emergência").
 * @param {"default" | "success" | "warning" | "danger"} [props.variant="default"] - Tom da barra.
 * @param {boolean} [props.showValue=true] - Exibe o percentual em texto.
 * @param {string} [props.valueLabel] - Texto alternativo ao percentual.
 */
import * as React from "react"
import { cn } from "../../lib/utils"

// Tons -600/-700 no claro e -500 no escuro mantêm >= 3:1 contra o trilho
// `bg-muted`, exigido para componentes de interface (WCAG 1.4.11).
const variantStyles = {
  default: "bg-primary",
  success: "bg-emerald-600 dark:bg-emerald-500",
  warning: "bg-amber-600 dark:bg-amber-500",
  danger: "bg-rose-600 dark:bg-rose-500",
}

const Progress = React.forwardRef(
  (
    {
      value = 0,
      max = 100,
      label,
      variant = "default",
      showValue = true,
      valueLabel,
      className,
      ...props
    },
    ref
  ) => {
    const safeMax = Number(max) > 0 ? Number(max) : 100
    const rawValue = Number.isFinite(Number(value)) ? Number(value) : 0
    const percent = (rawValue / safeMax) * 100
    const larguraVisual = Math.min(Math.max(percent, 0), 100)
    const percentTexto = `${percent.toFixed(percent >= 10 ? 0 : 1)}%`

    return (
      <div ref={ref} className={cn("space-y-1.5", className)} {...props}>
        {(label || showValue) && (
          <div className="flex items-baseline justify-between gap-2 text-xs">
            {label && <span className="font-medium text-muted-foreground">{label}</span>}
            {showValue && (
              <span className="font-semibold tabular-nums text-foreground">
                {valueLabel ?? percentTexto}
              </span>
            )}
          </div>
        )}
        <div
          role="progressbar"
          aria-valuenow={Math.round(percent)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
          aria-valuetext={valueLabel ? `${valueLabel} (${percentTexto})` : percentTexto}
          className="h-2 w-full overflow-hidden rounded-full border border-border/40 bg-muted"
        >
          <div
            className={cn("h-full rounded-full transition-all duration-500", variantStyles[variant])}
            style={{ width: `${larguraVisual}%` }}
          />
        </div>
      </div>
    )
  }
)
Progress.displayName = "Progress"

export { Progress }
