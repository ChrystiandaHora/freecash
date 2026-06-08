/**
 * Componente de Tabela de Dados Dinâmica Padronizada (DataTable).
 * 
 * Renderiza tabelas limpas, premium e responsivas seguindo as diretrizes do playbook
 * de frontend. Oferece paginação híbrida (local/servidor), ordenação de colunas (local/servidor),
 * sombras de overflow responsivas automáticas (via IntersectionObserver) e acessibilidade WCAG/WAI-ARIA.
 *
 * @component
 */
import * as React from "react"
import { useState, useMemo, useRef, useEffect } from "react"
import { 
  ArrowUpDown, ChevronUp, ChevronDown, 
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight 
} from "lucide-react"
import { cn } from "../../lib/utils"
import { Button } from "./Button"

const DataTable = ({
  columns = [],
  data = [],
  isLoading = false,
  emptyMessage = "Nenhum registro encontrado.",
  className,
  rowClassName,
  
  // Paginação Local (Client-side)
  pageSize,
  
  // Paginação Controlada (Server-side)
  currentPage,
  totalCount,
  onPageChange,
  
  // Ordenação Controlada (Server-side)
  sortKey,
  sortDir,
  onSort,

  // Ordenação Padrão (Uncontrolled)
  defaultSortKey = null,
  defaultSortDir = "asc",
}) => {
  // --- Estados Locais para Ordenação (Uncontrolled) ---
  const [localSortKey, setLocalSortKey] = useState(defaultSortKey)
  const [localSortDir, setLocalSortDir] = useState(defaultSortDir)

  // --- Estados Locais para Paginação (Uncontrolled) ---
  const [localPage, setLocalPage] = useState(1)

  // --- Reset da página local caso dados mudem ---
  useEffect(() => {
    setLocalPage(1)
  }, [data.length, pageSize])

  // --- Resolução de Ordenação Ativa ---
  const activeSortKey = sortKey !== undefined ? sortKey : localSortKey
  const activeSortDir = sortDir !== undefined ? sortDir : localSortDir

  const handleSortClick = (key) => {
    const isAsc = activeSortKey === key && activeSortDir === "asc"
    const nextDir = isAsc ? "desc" : "asc"

    if (onSort) {
      onSort(key, nextDir)
    } else {
      setLocalSortKey(key)
      setLocalSortDir(nextDir)
    }
  }

  // --- Processamento Local: Ordenação ---
  const sortedData = useMemo(() => {
    if (onSort) return data // Ordenação controlada por API externa

    if (!activeSortKey) return data

    return [...data].sort((a, b) => {
      const valA = a[activeSortKey]
      const valB = b[activeSortKey]

      if (valA === undefined || valA === null) return 1
      if (valB === undefined || valB === null) return -1

      // Função auxiliar para verificar se o valor é numérico ou uma string numérica válida
      const isNumeric = (val) => {
        if (typeof val === "number") return true
        if (typeof val === "string") {
          return val.trim() !== "" && !isNaN(Number(val))
        }
        return false
      }

      let comparison = 0
      if (isNumeric(valA) && isNumeric(valB)) {
        comparison = Number(valA) - Number(valB)
      } else if (
        !isNaN(Date.parse(valA)) && 
        !isNaN(Date.parse(valB)) && 
        typeof valA === "string" && 
        valA.includes("-")
      ) {
        // Ordenação inteligente de datas no formato YYYY-MM-DD
        comparison = new Date(valA) - new Date(valB)
      } else {
        comparison = String(valA).localeCompare(String(valB), undefined, { 
          numeric: true, 
          sensitivity: "base" 
        })
      }

      return activeSortDir === "asc" ? comparison : -comparison
    })
  }, [data, activeSortKey, activeSortDir, onSort])

  // --- Resolução de Paginação Ativa ---
  const isControlledPagination = currentPage !== undefined && onPageChange !== undefined
  const activePage = isControlledPagination ? currentPage : localPage

  // --- Resolução de Contagem Total de Itens ---
  const finalTotalCount = totalCount !== undefined ? totalCount : sortedData.length
  const finalPageSize = pageSize || 10
  const totalPages = Math.ceil(finalTotalCount / finalPageSize) || 1

  // --- Dados Paginados Finais ---
  const paginatedData = useMemo(() => {
    if (isControlledPagination || !pageSize) return sortedData

    const start = (activePage - 1) * finalPageSize
    return sortedData.slice(start, start + finalPageSize)
  }, [sortedData, activePage, finalPageSize, isControlledPagination, pageSize])

  // --- Handlers de Mudança de Página ---
  const goToPage = (page) => {
    const targetPage = Math.max(1, Math.min(page, totalPages))
    if (isControlledPagination) {
      onPageChange(targetPage)
    } else {
      setLocalPage(targetPage)
    }
  }

  // --- Estados de Rolagem e Sombras de Overflow ---
  const [showLeftShadow, setShowLeftShadow] = useState(false)
  const [showRightShadow, setShowRightShadow] = useState(false)

  const scrollerRef = useRef(null)
  const leftSentinelRef = useRef(null)
  const rightSentinelRef = useRef(null)

  useEffect(() => {
    if (!leftSentinelRef.current || !rightSentinelRef.current || !scrollerRef.current) return

    const leftObserver = new IntersectionObserver(
      ([entry]) => {
        // Se a sentinela não estiver intersectando, indica que há conteúdo oculto à esquerda
        setShowLeftShadow(!entry.isIntersecting)
      },
      { root: scrollerRef.current, threshold: 0 }
    )

    const rightObserver = new IntersectionObserver(
      ([entry]) => {
        // Se a sentinela não estiver intersectando, indica que há conteúdo oculto à direita
        setShowRightShadow(!entry.isIntersecting)
      },
      { root: scrollerRef.current, threshold: 0 }
    )

    leftObserver.observe(leftSentinelRef.current)
    rightObserver.observe(rightSentinelRef.current)

    return () => {
      leftObserver.disconnect()
      rightObserver.disconnect()
    }
  }, [data.length, isLoading])

  // --- Renderização do Esqueleto Skeletal (Loading State) ---
  if (isLoading) {
    return (
      <div className="w-full rounded-xl border border-border/60 overflow-hidden bg-card shadow-sm">
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
            {Array.from({ length: pageSize || 5 }).map((_, i) => (
              <tr key={i} className="border-b border-border/40 last:border-0">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-4">
                    <div className="h-4 animate-pulse rounded bg-muted/70 w-3/4" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // --- Estilos de Isolamento de Renderização em Inline Styles ---
  const datatableStyle = {
    contentVisibility: "auto",
    containIntrinsicSize: "auto 400px"
  }

  return (
    <div 
      className={cn("w-full bg-card rounded-xl border border-border/60 shadow-sm relative overflow-hidden", className)}
      style={datatableStyle}
    >
      {/* Estilos adicionais injetados para degradação graciosa do content-visibility */}
      <style dangerouslySetInnerHTML={{__html: `
        @supports not (content-visibility: auto) {
          .datatable-container {
            contain: layout style paint;
          }
        }
      `}} />

      {/* Indicadores Visuais de Sombras de Overflow */}
      <div className={cn("absolute left-0 top-0 bottom-0 w-8 pointer-events-none transition-opacity duration-300 bg-gradient-to-r from-background/80 to-transparent z-10", showLeftShadow ? "opacity-100" : "opacity-0")} />
      <div className={cn("absolute right-0 top-0 bottom-0 w-8 pointer-events-none transition-opacity duration-300 bg-gradient-to-l from-background/80 to-transparent z-10", showRightShadow ? "opacity-100" : "opacity-0")} />

      {/* Container de Rolagem Horizontal */}
      <div 
        ref={scrollerRef}
        className="w-full overflow-x-auto scroller relative container-scroll-state"
      >
        {/* Sentinela de Borda Esquerda */}
        <div ref={leftSentinelRef} className="absolute left-0 top-0 w-px h-full pointer-events-none" />

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/40">
              {columns.map((col) => {
                const isSortable = col.sortable !== false && !!col.key
                const isCurrentlySorted = activeSortKey === col.key

                return (
                  <th 
                    key={col.key} 
                    scope="col"
                    className={cn(
                      "px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap",
                      isSortable && "cursor-pointer select-none hover:bg-muted/60 transition-colors",
                      col.className
                    )}
                    onClick={() => isSortable && handleSortClick(col.key)}
                  >
                    <div className="flex items-center gap-1.5">
                      {col.header}
                      {isSortable && (
                        <span className="text-muted-foreground/60 transition-colors duration-150">
                          {isCurrentlySorted ? (
                            activeSortDir === "asc" ? (
                              <ChevronUp className="h-4 w-4 text-primary" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-primary" />
                            )
                          ) : (
                            <ArrowUpDown className="h-3.5 w-3.5 opacity-40 hover:opacity-100" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-16 text-center text-muted-foreground">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              paginatedData.map((row, idx) => (
                <tr
                  key={row.id ?? idx}
                  className={cn(
                    "border-b border-border/40 last:border-0 transition-colors duration-150 hover:bg-muted/20",
                    rowClassName && rowClassName(row)
                  )}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={cn("px-4 py-3 align-middle", col.cellClassName)}>
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Sentinela de Borda Direita */}
        <div ref={rightSentinelRef} className="absolute right-0 top-0 w-px h-full pointer-events-none" />
      </div>

      {/* --- Footer de Paginação Acessível --- */}
      {pageSize && totalPages > 1 && (
        <div 
          className="border-t border-border/40 px-4 py-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-muted/20"
          aria-label="Controle de Paginação"
        >
          {/* Status Text */}
          <span className="text-xs text-muted-foreground font-medium">
            Mostrando <span className="font-semibold text-foreground">{(activePage - 1) * finalPageSize + 1}</span> a{" "}
            <span className="font-semibold text-foreground">
              {Math.min(activePage * finalPageSize, finalTotalCount)}
            </span>{" "}
            de <span className="font-semibold text-foreground">{finalTotalCount}</span> registros
          </span>

          {/* Navigation Controls */}
          <div className="flex items-center justify-center gap-1.5">
            {/* Primeira Página */}
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 p-0"
              onClick={() => goToPage(1)}
              disabled={activePage === 1}
              aria-label="Ir para a primeira página"
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>

            {/* Página Anterior */}
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 p-0"
              onClick={() => goToPage(activePage - 1)}
              disabled={activePage === 1}
              aria-label="Ir para a página anterior"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            {/* Lista Compacta de Páginas */}
            <div className="flex items-center gap-1 mx-1.5">
              {Array.from({ length: totalPages }).map((_, i) => {
                const pageNum = i + 1
                // Renderizar botão se for a página atual ou as 2 adjacentes
                const isNear = Math.abs(activePage - pageNum) <= 1
                const isEdges = pageNum === 1 || pageNum === totalPages

                if (!isNear && !isEdges) {
                  // Retornar reticências caso haja páginas omitidas
                  if (pageNum === 2 || pageNum === totalPages - 1) {
                    return <span key={pageNum} className="text-muted-foreground/60 text-xs px-1">...</span>
                  }
                  return null
                }

                return (
                  <Button
                    key={pageNum}
                    variant={activePage === pageNum ? "default" : "outline"}
                    className={cn(
                      "h-8 w-8 text-xs p-0 font-semibold transition-all duration-150",
                      activePage === pageNum 
                        ? "bg-primary text-primary-foreground border-transparent shadow-sm"
                        : "hover:bg-muted text-muted-foreground hover:text-foreground"
                    )}
                    onClick={() => goToPage(pageNum)}
                    aria-label={`Ir para a página ${pageNum}`}
                    aria-current={activePage === pageNum ? "page" : undefined}
                  >
                    {pageNum}
                  </Button>
                )
              })}
            </div>

            {/* Próxima Página */}
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 p-0"
              onClick={() => goToPage(activePage + 1)}
              disabled={activePage === totalPages}
              aria-label="Ir para a próxima página"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>

            {/* Última Página */}
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 p-0"
              onClick={() => goToPage(totalPages)}
              disabled={activePage === totalPages}
              aria-label="Ir para a última página"
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export { DataTable }
