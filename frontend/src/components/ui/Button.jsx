/**
 * Componente de Botão de Ação Interativo.
 * 
 * Um botão customizável construído sobre o elemento nativo HTML `<button>` que suporta
 * variantes visuais pré-definidas (glassmorphism/flat), tamanhos configuráveis e
 * encaminhamento de referências do DOM (forwardRef).
 *
 * @component
 * @param {Object} props - Propriedades de configuração do botão.
 * @param {string} [props.className] - Classes CSS adicionais do Tailwind para estilização customizada.
 * @param {"default" | "destructive" | "outline" | "secondary" | "ghost" | "link"} [props.variant="default"] - Variante visual e temática do botão.
 * @param {"default" | "sm" | "lg" | "icon"} [props.size="default"] - Dimensões e espaçamentos do botão.
 * @param {React.ButtonHTMLAttributes<HTMLButtonElement>} props - Demais propriedades nativas do elemento HTML `<button>`.
 * @param {React.Ref<HTMLButtonElement>} ref - Referência DOM encaminhada para o botão.
 * @returns {React.JSX.Element} Elemento JSX do botão renderizado.
 */
import * as React from "react"
import { cn } from "../../lib/utils"

const Button = React.forwardRef(({ className, variant = "default", size = "default", ...props }, ref) => {
  const baseStyles = "inline-flex items-center justify-center rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]"
  
  const variants = {
    default: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-md shadow-primary/10",
    destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-md shadow-destructive/10",
    outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    ghost: "hover:bg-accent hover:text-accent-foreground",
    link: "text-primary underline-offset-4 hover:underline",
  }

  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-9 rounded-md px-3",
    lg: "h-11 rounded-md px-8 text-base",
    icon: "h-10 w-10",
  }

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      ref={ref}
      {...props}
    />
  )
})
Button.displayName = "Button"

export { Button }
