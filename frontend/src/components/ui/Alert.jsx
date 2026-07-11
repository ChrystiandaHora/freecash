/**
 * Banner de mensagem contextual (erro, sucesso, aviso ou informação).
 *
 * Padroniza as caixas de mensagem coloridas usadas em todas as telas, reutilizando
 * a mesma paleta semântica já estabelecida pelo componente Badge.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {"error" | "success" | "warning" | "info"} [props.variant="info"] - Estilo temático da mensagem.
 * @param {React.ComponentType} [props.icon] - Componente de ícone (lucide-react) exibido à esquerda.
 * @param {string} [props.title] - Título curto em destaque, exibido acima do conteúdo.
 * @param {string} [props.className] - Estilos CSS extras do Tailwind.
 * @param {React.ReactNode} props.children - Conteúdo da mensagem.
 * @returns {React.JSX.Element} Elemento JSX do Alert renderizado.
 *
 * Nota de acessibilidade: os tons de texto de cada variante foram escolhidos
 * para manter contraste >= 4.5:1 (WCAG AA / WAVE) mesmo contra o fundo mais
 * claro do tema (`--background: #eee`) — por isso `success`/`warning` usam
 * -800 em vez de -600 (que falha: ~3.2:1 a ~3.8:1 nesse fundo).
 */
import { cn } from "../../lib/utils"

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
    >
      {Icon && <Icon className="h-4 w-4 shrink-0 mt-0.5" />}
      <div className="flex-1 min-w-0 space-y-1">
        {title && <h4 className={cn("text-xs font-bold", titleStyles[variant])}>{title}</h4>}
        <div className={title ? "text-[11px] opacity-80" : undefined}>{children}</div>
      </div>
    </div>
  )
}
