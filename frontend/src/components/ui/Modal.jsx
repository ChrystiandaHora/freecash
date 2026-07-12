/**
 * Componente de Caixa de Diálogo Flutuante (Modal).
 * 
 * Renderiza uma janela sobreposta (com backdrop escurecido e blur de fundo) para
 * exibição de formulários operacionais (criar ativo, liquidar contas), contendo escuta
 * nativa para fechamento ao teclar Escape ou clicar fora da janela.
 *
 * @component
 * @param {Object} props - Propriedades de configuração do Modal.
 * @param {boolean} props.isOpen - Indica se a modal está visível na tela.
 * @param {Function} props.onClose - Callback disparado para solicitar o fechamento da modal.
 * @param {string} [props.title] - O título do cabeçalho da modal.
 * @param {string} [props.description] - Subtítulo descritivo secundário.
 * @param {React.ReactNode} props.children - Conteúdo do corpo interno a ser renderizado.
 * @param {string} [props.className] - Estilos CSS extras do Tailwind para o container do diálogo.
 * @param {"sm" | "md" | "lg" | "xl"} [props.size="md"] - Largura máxima pré-definida para a modal.
 * @returns {React.JSX.Element | null} Elemento JSX ou null caso esteja fechada.
 */
import { useEffect, useRef } from "react"
import { cn } from "../../lib/utils"
import { X } from "lucide-react"

const Modal = ({ isOpen, onClose, title, description, children, className, size = "md" }) => {
  const overlayRef = useRef(null)

  const sizeClasses = {
    sm: "max-w-md",
    md: "max-w-lg",
    lg: "max-w-2xl",
    xl: "max-w-4xl",
  }

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape" && isOpen) onClose()
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [isOpen, onClose])

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-modal="true"
      role="dialog"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        className={cn(
          "relative z-10 w-full rounded-xl border border-border bg-card shadow-2xl animate-in zoom-in-95 fade-in duration-200",
          sizeClasses[size],
          className
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-4 border-b border-border/60">
          <div>
            {title && (
              <h2 id="modal-title" className="text-lg font-semibold text-foreground">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-4 rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            aria-label="Fechar modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}

Modal.displayName = "Modal"

export { Modal }
