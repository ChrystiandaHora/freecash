/**
 * Componentes de Acordeão (Accordion) para Colapso de Conteúdo.
 * 
 * Abstrai seções expansíveis e agrupamentos hierárquicos com transições de altura suaves.
 *
 * @module Accordion
 */

import * as React from "react"
import { useState } from "react"
import { cn } from "../../lib/utils"
import { ChevronDown } from "lucide-react"


/**
 * Item expansível individual do Acordeão.
 * 
 * Controla seu próprio estado aberto/fechado local e renderiza o gatilho de cabeçalho
 * e a seção de conteúdo colapsável.
 *
 * @component
 * @param {Object} props - Propriedades do item.
 * @param {string} props.title - O título descritivo exibido no gatilho do acordeão.
 * @param {React.ReactNode} props.children - Conteúdo revelado ao expandir o item.
 * @param {string} [props.className] - Classes CSS extras para o container externo.
 * @param {React.HTMLAttributes<HTMLDivElement>} props - Demais atributos nativos de elemento HTML `<div>`.
 * @param {React.Ref<HTMLDivElement>} ref - Referência DOM encaminhada para o container externo.
 * @returns {React.JSX.Element}
 */
export const AccordionItem = React.forwardRef(({ title, children, className, ...props }, ref) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div 
      ref={ref} 
      className={cn("border-b border-border/60 py-1 transition-all duration-300", className)} 
      {...props}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between py-3 text-sm font-medium transition-all hover:text-primary text-left text-foreground/80"
      >
        <span className="font-semibold">{title}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300",
            isOpen && "rotate-180"
          )}
        />
      </button>
      <div
        className={cn(
          "grid transition-all duration-300 ease-in-out text-sm overflow-hidden",
          isOpen ? "grid-rows-[1fr] opacity-100 py-2" : "grid-rows-[0fr] opacity-0"
        )}
      >
        <div className="overflow-hidden">{children}</div>
      </div>
    </div>
  )
})
AccordionItem.displayName = "AccordionItem"


/**
 * Container unificado do Acordeão.
 * 
 * Agrupa múltiplos elementos `AccordionItem` organizando-os em uma pilha vertical.
 *
 * @component
 * @param {Object} props - Propriedades do Accordion.
 * @param {React.ReactNode} props.children - Coleção de elementos AccordionItem.
 * @param {string} [props.className] - Estilos CSS extras do Tailwind.
 * @returns {React.JSX.Element}
 */
export const Accordion = ({ children, className }) => {
  return (
    <div className={cn("w-full space-y-1", className)}>
      {children}
    </div>
  )
}

