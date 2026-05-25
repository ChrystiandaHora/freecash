/**
 * Componente de Tabela de Dados Dinâmica (DataTable).
 * 
 * Renderiza tabelas limpas e responsivas com suporte a colunas dinâmicas configuráveis,
 * renderizadores customizados por célula, carregamento com animação esquelética (skeleton pulse)
 * e mensagem customizada de registros vazios.
 *
 * @component
 * @param {Object} props - Propriedades de configuração da tabela.
 * @param {Array<{key: string, header: string, render?: Function, className?: string, cellClassName?: string}>} props.columns - Definição das colunas.
 * @param {Object[]} props.data - Coleção de registros de dados a serem listados.
 * @param {boolean} [props.isLoading=false] - Flag indicando se o esqueleto de carregamento deve ser exibido.
 * @param {string} [props.emptyMessage="Nenhum registro encontrado."] - Mensagem exibida caso a coleção esteja vazia.
 * @param {string} [props.className] - Estilos CSS extras do Tailwind para a borda da tabela.
 * @param {Function} [props.rowClassName] - Função callback geradora de classe condicional para as linhas.
 * @returns {React.JSX.Element} Elemento JSX representando a tabela estruturada.
 */
import * as React from "react"
import { cn } from "../../lib/utils"

const DataTable = ({ columns = [], data = [], isLoading = false, emptyMessage = "Nenhum registro encontrado.", className, rowClassName }) => {
  if (isLoading) {
    return (
      <div className="w-full overflow-x-auto rounded-xl border border-border/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/40">
              {columns.map((col) => (
                <th key={col.key} className={cn("px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap", col.className)}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b border-border/40 last:border-0">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3">
                    <div className="h-4 animate-pulse rounded bg-muted" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="w-full overflow-x-auto rounded-xl border border-border/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/40">
              {columns.map((col) => (
                <th key={col.key} className={cn("px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap", col.className)}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={columns.length} className="px-4 py-16 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className={cn("w-full overflow-x-auto rounded-xl border border-border/60", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/60 bg-muted/40">
            {columns.map((col) => (
              <th key={col.key} className={cn("px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap", col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr
              key={row.id ?? idx}
              className={cn(
                "border-b border-border/40 last:border-0 transition-colors duration-150 hover:bg-muted/30",
                rowClassName && rowClassName(row)
              )}
            >
              {columns.map((col) => (
                <td key={col.key} className={cn("px-4 py-3", col.cellClassName)}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export { DataTable }
