/**
 * Banner de mensagem contextual (erro, sucesso, aviso ou informação).
 *
 * Padroniza as caixas coloridas de todas as telas, reutilizando a paleta semântica do
 * componente Badge.
 *
 * @param {"error" | "success" | "warning" | "info"} [props.variant="info"] - Estilo da mensagem.
 * @param {React.ComponentType} [props.icon] - Ícone (lucide-react) exibido à esquerda.
 * @param {string} [props.title] - Título curto em destaque.
 * @param {React.ReactNode} props.children - Conteúdo da mensagem.
 *
 * Acessibilidade: os tons de texto mantêm contraste >= 4.5:1 mesmo contra o fundo mais
 * claro do tema, por isso `success`/`warning` usam -800 em vez de -600 (que fica em
 * ~3.2:1). O `role` deriva da variante (WCAG 4.1.3): `alert` para erro e aviso,
 * `status` para sucesso e informação — sem `aria-live` explícito, já implícito no role.
 */
import { cn } from "../../lib/utils"

const roleByVariant = {
  error: "alert",
  warning: "alert",
  success: "status",
  info: "status",
}

const variantStyles = {
  error: "border-red-500/20 bg-red-500/5 text-red-700 dark:text-red-400",
  success: "border-emerald-500/20 bg-emerald-500/5 text-emerald-800 dark:text-emerald-400",
  warning: "border-amber-500/20 bg-amber-500/5 text-amber-800 dark:text-amber-400",
  info: "border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400",
}

const titleStyles = {
  error: "text-red-700 dark:text-red-300",
  success: "text-emerald-800 dark:text-emerald-300",
  warning: "text-amber-800 dark:text-amber-300",
  info: "text-blue-800 dark:text-blue-300",
}

export function Alert({ variant = "info", icon: Icon, title, className, children, ...props }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border p-4 text-sm",
        variantStyles[variant],
        className
      )}
      {...props}
      role={roleByVariant[variant]}
    >
      {Icon && <Icon className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />}
      <div className="flex-1 min-w-0 space-y-1">
        {title && <h4 className={cn("text-xs font-bold", titleStyles[variant])}>{title}</h4>}
        <div className={title ? "text-xs opacity-80" : undefined}>{children}</div>
      </div>
    </div>
  )
}
