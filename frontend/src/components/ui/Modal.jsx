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
 * @param {string} [props.ariaLabel] - Nome acessível alternativo, usado apenas quando `title` não é passado.
 * @returns {React.JSX.Element | null} Elemento JSX ou null caso esteja fechada.
 *
 * Nota de acessibilidade: ao abrir, o foco é movido para o primeiro elemento
 * focável do diálogo e fica trapeado dentro dele (Tab/Shift+Tab cicla só entre
 * os elementos internos); ao fechar, o foco retorna ao elemento que abriu a
 * modal (WCAG 2.4.3).
 */
import { useEffect, useId, useRef } from "react"
import { cn } from "../../lib/utils"
import { X } from "lucide-react"

const FOCUSABLE_SELECTOR =
  'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

const Modal = ({ isOpen, onClose, title, description, children, className, size = "md", ariaLabel }) => {
  const overlayRef = useRef(null)
  const panelRef = useRef(null)
  const previouslyFocusedRef = useRef(null)
  // Id único por instância: um literal fixo colidiria quando duas modais
  // coexistem no DOM (ex.: modal da página + modal de Ajuda do layout).
  const titleId = useId()

  const sizeClasses = {
    sm: "max-w-md",
    md: "max-w-lg",
    lg: "max-w-2xl",
    xl: "max-w-4xl",
  }

  const getFocusable = () =>
    Array.from(panelRef.current?.querySelectorAll(FOCUSABLE_SELECTOR) ?? []).filter(
      (el) => !el.disabled
    )

  useEffect(() => {
    if (!isOpen) return

    const handleKey = (e) => {
      if (e.key === "Escape") {
        onClose()
        return
      }

      if (e.key !== "Tab") return

      const focusable = getFocusable()
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      // Se o foco escapou do painel (o fundo não é inert), traz de volta.
      if (!panelRef.current?.contains(active)) {
        e.preventDefault()
        first.focus()
        return
      }

      if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [isOpen, onClose])

  useEffect(() => {
    if (!isOpen) return

    document.body.style.overflow = "hidden"
    previouslyFocusedRef.current = document.activeElement
    getFocusable()[0]?.focus()

    // A restauração vive no cleanup — não num `else` — para cobrir também os
    // call sites que montam a modal condicionalmente (`{cond && <Modal isOpen>}`)
    // e portanto desmontam sem nunca renderizar com isOpen=false.
    return () => {
      document.body.style.overflow = ""

      const trigger = previouslyFocusedRef.current
      // O gatilho pode ter saído do DOM (ex.: o botão da linha que a exclusão
      // acabou de remover); nesse caso .focus() seria um no-op silencioso e o
      // foco cairia no <body>. Recai para a região de conteúdo principal.
      if (trigger?.isConnected) {
        trigger.focus()
      } else {
        document.getElementById("conteudo-principal")?.focus()
      }
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-modal="true"
      role="dialog"
      aria-labelledby={title ? titleId : undefined}
      aria-label={!title ? ariaLabel : undefined}
    >
      {/* Backdrop — puramente visual: o fechamento por teclado é feito via Escape
          e pelo botão de fechar, então não expõe nome/foco próprios. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        ref={panelRef}
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
              <h2 id={titleId} className="text-lg font-semibold text-foreground">
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
