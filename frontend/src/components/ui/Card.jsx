/**
 * Componentes de Painel (Card) de Conteúdo Estruturado.
 * 
 * Agrupa utilitários para criar painéis de informação contendo cabeçalhos, rodapés,
 * títulos e containers de conteúdo flexíveis.
 *
 * @module Card
 */

import * as React from "react"
import { cn } from "../../lib/utils"


/**
 * Container principal do Painel (Card).
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS adicionais do Tailwind.
 * @param {React.HTMLAttributes<HTMLDivElement>} props - Atributos HTML `<div>`.
 * @param {React.Ref<HTMLDivElement>} ref - Referência DOM encaminhada.
 * @returns {React.JSX.Element}
 */
const Card = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-xl border bg-card text-card-foreground shadow-sm transition-all duration-300 hover:shadow-md",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"


/**
 * Cabeçalho do Painel.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS extras.
 * @param {React.HTMLAttributes<HTMLDivElement>} props - Atributos HTML `<div>`.
 * @param {React.Ref<HTMLDivElement>} ref - Referência DOM.
 * @returns {React.JSX.Element}
 */
const CardHeader = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"


/**
 * Título principal do Painel.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS extras.
 * @param {React.HTMLAttributes<HTMLHeadingElement>} props - Atributos de cabeçalho `<h3>`.
 * @param {React.Ref<HTMLHeadingElement>} ref - Referência DOM.
 * @returns {React.JSX.Element}
 */
const CardTitle = React.forwardRef(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"


/**
 * Subtítulo ou descrição secundária do Painel.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS extras.
 * @param {React.HTMLAttributes<HTMLParagraphElement>} props - Atributos de parágrafo `<p>`.
 * @param {React.Ref<HTMLParagraphElement>} ref - Referência DOM.
 * @returns {React.JSX.Element}
 */
const CardDescription = React.forwardRef(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"


/**
 * Container principal para o corpo/conteúdo do Painel.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS extras.
 * @param {React.HTMLAttributes<HTMLDivElement>} props - Atributos HTML `<div>`.
 * @param {React.Ref<HTMLDivElement>} ref - Referência DOM.
 * @returns {React.JSX.Element}
 */
const CardContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"


/**
 * Rodapé do Painel, ideal para botões de ação ou links de rodapé.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} [props.className] - Estilos CSS extras.
 * @param {React.HTMLAttributes<HTMLDivElement>} props - Atributos HTML `<div>`.
 * @param {React.Ref<HTMLDivElement>} ref - Referência DOM.
 * @returns {React.JSX.Element}
 */
const CardFooter = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }

