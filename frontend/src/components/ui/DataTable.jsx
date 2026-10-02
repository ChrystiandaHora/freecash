/**
 * Componente de Tabela de Dados Dinâmica Padronizada (DataTable).
 *
 * Renderiza tabelas limpas, premium e responsivas seguindo as diretrizes do playbook
 * de frontend. Oferece paginação híbrida (local/servidor), ordenação de colunas (local/servidor),
 * filtros individuais por coluna (local/servidor), sombras de overflow responsivas automáticas
 * (via IntersectionObserver) e acessibilidade WCAG/WAI-ARIA.
 */
import { useState, useMemo, useRef, useEffect, useCallback } from "react"
import { createPortal } from "react-dom"

import { DateRangeCalendar } from "./DateRangeCalendar"
import {
  ArrowUpDown, ChevronUp, ChevronDown,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  Filter, X
} from "lucide-react"
import { cn } from "../../lib/utils"
import { Button } from "./Button"
import {
  getFilterValue,
  isFilterActive,
  resolveFilterTypes,
  applyColumnFilters,
  describeAppliedFilters,
} from "./columnFilters"

const headerLabel = (col) => (typeof col.header === "string" ? col.header : col.key)

/** Resumo dos filtros aplicados, em chips removíveis. */
const AppliedFiltersBar = ({ appliedFilters, onClear, onClearAll, className }) => {
  if (appliedFilters.length === 0) return null
  return (
    <div
      className={cn("flex flex-wrap items-center gap-2 border-b border-border/40 bg-muted/20 px-4 py-2.5", className)}
      aria-label="Filtros aplicados"
    >
      <span className="text-xs font-medium text-muted-foreground">Filtros:</span>
      {appliedFilters.map(({ col, label }) => (
        <span
          key={col.key}
          className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-card px-2.5 py-1 text-xs text-foreground"
        >
          <span className="font-medium text-muted-foreground">{headerLabel(col)}:</span>
          <span className="max-w-48 truncate">{label}</span>
          <button
            type="button"
            onClick={() => onClear(col.key)}
            aria-label={`Remover filtro de ${headerLabel(col)}`}
            className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-3 w-3" aria-hidden="true" />
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={onClearAll}
        className="ml-auto text-xs font-semibold text-primary transition-opacity hover:opacity-80"
      >
        Limpar todos
      </button>
    </div>
  )
}

/**
 * Popover de filtro individual de coluna, renderizado em portal para escapar
 * do recorte imposto pelo container de rolagem horizontal da tabela.
 */
const ColumnFilterPopover = ({ column, type, value, anchorRect, data = [], onChange, onClear, onClose }) => {
  const panelRef = useRef(null)

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (panelRef.current?.contains(event.target)) return
      // Cliques no próprio gatilho são tratados pelo botão (evita reabertura imediata)
      if (event.target.closest?.("[data-filter-trigger]")) return
      onClose()
    }
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose()
    }

    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    window.addEventListener("resize", onClose)
    window.addEventListener("scroll", onClose, true)

    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("resize", onClose)
      window.removeEventListener("scroll", onClose, true)
    }
  }, [onClose])

  // O filtro de data abriga uma grade de sete colunas e precisa de mais espaço que
  // os demais tipos, que são um ou dois campos em coluna.
  const PANEL_WIDTH = type === "date" ? 300 : 248
  const style = {
    position: "fixed",
    top: anchorRect.bottom + 6,
    left: Math.max(8, Math.min(anchorRect.left, window.innerWidth - PANEL_WIDTH - 8)),
    width: PANEL_WIDTH,
    zIndex: 60,
  }

  const inputClass =
    "w-full h-9 rounded-md border border-border bg-background px-2.5 text-sm text-foreground " +
    "placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-primary/40"

  return createPortal(
    <div
      ref={panelRef}
      style={style}
      role="dialog"
      aria-label={`Filtrar por ${typeof column.header === "string" ? column.header : column.key}`}
      className="rounded-lg border border-border bg-card p-3 shadow-lg animate-in zoom-in-95 fade-in duration-200"
      onClick={(e) => e.stopPropagation()}
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Filtrar
      </p>

      {type === "date" && (
        <DateRangeCalendar
          value={value}
          onChange={onChange}
          inputClass={inputClass}
        />
      )}

      {type === "number" && (
        <div className="flex items-end gap-2">
          <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-muted-foreground">
            Mín.
            <input
              type="number"
              autoFocus
              className={inputClass}
              value={value?.min ?? ""}
              onChange={(e) => onChange({ ...value, min: e.target.value })}
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-muted-foreground">
            Máx.
            <input
              type="number"
              className={inputClass}
              value={value?.max ?? ""}
              onChange={(e) => onChange({ ...value, max: e.target.value })}
            />
          </label>
        </div>
      )}

      {type === "boolean" && (
        <select
          autoFocus
          aria-label={`Valor do filtro de ${typeof column.header === "string" ? column.header : column.key}`}
          className={inputClass}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Todos</option>
          <option value="true">{column.filterTrueLabel ?? "Sim"}</option>
          <option value="false">{column.filterFalseLabel ?? "Não"}</option>
        </select>
      )}

      {type === "select" && (
        <select
          autoFocus
          aria-label={`Valor do filtro de ${typeof column.header === "string" ? column.header : column.key}`}
          className={inputClass}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Todos</option>
          {((column.filterOptions && column.filterOptions.length > 0)
            ? column.filterOptions
            : Array.from(
                new Set(
                  (data || [])
                    .map((row) => getFilterValue(column, row))
                    .filter((val) => val !== null && val !== undefined && val !== "")
                    .map((val) => String(val))
                )
              ).sort((a, b) => a.localeCompare(b, 'pt-BR'))
          ).map((opt) => {
            const optValue = typeof opt === "object" ? opt.value : opt
            const optLabel = typeof opt === "object" ? opt.label : opt
            return (
              <option key={optValue} value={optValue}>
                {optLabel}
              </option>
            )
          })}
        </select>
      )}

      {type === "text" && (
        <input
          type="text"
          autoFocus
          aria-label={`Valor do filtro de ${typeof column.header === "string" ? column.header : column.key}`}
          placeholder={column.filterPlaceholder ?? "Buscar..."}
          className={inputClass}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      <div className="mt-3 flex justify-between gap-2">
        <button
          type="button"
          onClick={onClear}
          className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          Limpar
        </button>
        <button
          type="button"
          onClick={onClose}
          className="text-xs font-semibold text-primary transition-opacity hover:opacity-80"
        >
          Fechar
        </button>
      </div>
    </div>,
    document.body
  )
}

/**
 * Barra de filtros por coluna para visões dos mesmos dados que não são a tabela
 * (ex.: o kanban de Contas a Pagar). Usa as mesmas regras e o mesmo popover dos
 * cabeçalhos, então um filtro criado aqui ou na tabela significa a mesma coisa.
 */
const FilterToolbar = ({ columns = [], data = [], filters = {}, onFilterChange, className }) => {
  const [openFilterKey, setOpenFilterKey] = useState(null)
  const [anchorRect, setAnchorRect] = useState(null)
  const triggerRef = useRef(null)

  const filterTypes = useMemo(() => resolveFilterTypes(columns, data), [columns, data])
  const appliedFilters = describeAppliedFilters(columns, filters, filterTypes)
  const filterableColumns = columns.filter((col) => filterTypes[col.key])

  // Ao fechar, o foco volta ao botão que abriu o popover (WCAG 2.4.3)
  const closeFilter = useCallback(() => {
    setOpenFilterKey(null)
    setAnchorRect(null)
    triggerRef.current?.focus({ preventScroll: true })
  }, [])

  const handleToggle = (event, key) => {
    event.stopPropagation()
    if (openFilterKey === key) {
      closeFilter()
      return
    }
    triggerRef.current = event.currentTarget
    setAnchorRect(event.currentTarget.getBoundingClientRect())
    setOpenFilterKey(key)
  }

  const clearFilter = (key) => {
    const next = { ...filters }
    delete next[key]
    onFilterChange(next)
  }

  return (
    <div className={cn("overflow-hidden rounded-xl border border-border/60 bg-card", className)}>
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
        <span className="text-xs font-medium text-muted-foreground">Filtrar por:</span>
        {filterableColumns.map((col) => {
          const active = isFilterActive(filterTypes[col.key], filters[col.key])
          const open = openFilterKey === col.key
          return (
            <button
              key={col.key}
              type="button"
              data-filter-trigger={col.key}
              onClick={(e) => handleToggle(e, col.key)}
              aria-haspopup="dialog"
              aria-expanded={open}
              className={cn(
                "inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors",
                "focus:outline-none focus:ring-2 focus:ring-primary/40",
                active || open
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border/60 text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Filter className="h-3 w-3" aria-hidden="true" fill={active ? "currentColor" : "none"} />
              {headerLabel(col)}
              {active && <span className="sr-only"> (filtro ativo)</span>}
            </button>
          )
        })}
      </div>

      <AppliedFiltersBar
        appliedFilters={appliedFilters}
        onClear={clearFilter}
        onClearAll={() => onFilterChange({})}
        className="border-b-0 border-t"
      />

      {openFilterKey && anchorRect && (
        <ColumnFilterPopover
          column={columns.find((col) => col.key === openFilterKey)}
          type={filterTypes[openFilterKey]}
          value={filters[openFilterKey]}
          anchorRect={anchorRect}
          data={data}
          onChange={(value) => onFilterChange({ ...filters, [openFilterKey]: value })}
          onClear={() => clearFilter(openFilterKey)}
          onClose={closeFilter}
        />
      )}
    </div>
  )
}

const DataTable = ({
  columns = [],
  data = [],
  isLoading = false,
  emptyMessage = "Nenhum registro encontrado.",
  caption,
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

  // Filtros por Coluna
  filterable = true,
  defaultFilters = {},

  // Filtros Controlados: o pai guarda o estado; a filtragem segue local,
  // salvo com `manualFiltering`, quando os dados já chegam filtrados do servidor
  filters,
  onFilterChange,
  manualFiltering = false,

  // Callback ao alterar dados filtrados (para atualizar cards/KPIs no pai)
  onFilteredDataChange,
}) => {
  // --- Estados Locais para Ordenação (Uncontrolled) ---
  const [localSortKey, setLocalSortKey] = useState(defaultSortKey)
  const [localSortDir, setLocalSortDir] = useState(defaultSortDir)

  // --- Estados Locais para Paginação (Uncontrolled) ---
  const [localPage, setLocalPage] = useState(1)

  // --- Estados Locais para Filtros (Uncontrolled) ---
  const [localFilters, setLocalFilters] = useState(defaultFilters)
  const [openFilterKey, setOpenFilterKey] = useState(null)
  const [anchorRect, setAnchorRect] = useState(null)

  // --- Resolução de Filtros Ativos ---
  const activeFilters = filters !== undefined ? filters : localFilters
  const filterSignature = JSON.stringify(activeFilters)

  // --- Reset da página local caso dados ou filtros mudem ---
  useEffect(() => {
    setLocalPage(1)
  }, [data.length, pageSize, filterSignature])

  // --- Mapa de Tipos de Filtro por Coluna ---
  const filterTypes = useMemo(
    () => resolveFilterTypes(columns, data, filterable),
    [columns, data, filterable]
  )

  const closeFilter = useCallback(() => {
    setOpenFilterKey(null)
    setAnchorRect(null)
  }, [])

  const handleFilterToggle = (event, key) => {
    event.stopPropagation()
    if (openFilterKey === key) {
      closeFilter()
      return
    }
    setAnchorRect(event.currentTarget.getBoundingClientRect())
    setOpenFilterKey(key)
  }

  const applyFilters = (nextFilters) => {
    if (onFilterChange) {
      onFilterChange(nextFilters)
    } else {
      setLocalFilters(nextFilters)
      setLocalPage(1)
    }
  }

  const handleFilterValueChange = (key, value) => {
    applyFilters({ ...activeFilters, [key]: value })
  }

  const handleFilterClear = (key) => {
    const next = { ...activeFilters }
    delete next[key]
    applyFilters(next)
  }

  const handleClearAllFilters = () => applyFilters({})

  // --- Colunas com Filtro Ativo (usadas nos chips de resumo) ---
  const appliedFilters = useMemo(
    () => describeAppliedFilters(columns, activeFilters, filterTypes),
    [columns, filterTypes, activeFilters]
  )

  // --- Processamento Local: Filtragem ---
  const filteredData = useMemo(() => {
    if (manualFiltering) return data
    return applyColumnFilters(columns, data, activeFilters, filterTypes)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, columns, filterTypes, filterSignature, manualFiltering])

  // --- Notificar o componente pai sobre os dados filtrados ---
  const lastEmittedRef = useRef(null)
  useEffect(() => {
    if (!onFilteredDataChange) return

    const prev = lastEmittedRef.current
    const curr = filteredData

    if (prev && prev.length === curr.length) {
      let isSame = true
      for (let i = 0; i < curr.length; i++) {
        if (prev[i] !== curr[i] && (prev[i]?.id === undefined || prev[i]?.id !== curr[i]?.id)) {
          isSame = false
          break
        }
      }
      if (isSame) return
    }

    lastEmittedRef.current = curr
    onFilteredDataChange(curr)
  }, [filteredData, onFilteredDataChange])

  // --- Resolução de Ordenação Ativa ---
  const activeSortKey = sortKey !== undefined ? sortKey : localSortKey
  const activeSortDir = sortDir !== undefined ? sortDir : localSortDir

  const handleSortClick = (key) => {
    let nextKey = key
    let nextDir = "asc"

    if (activeSortKey === key) {
      if (activeSortDir === "asc") {
        nextDir = "desc"
      } else if (activeSortDir === "desc") {
        nextKey = null
        nextDir = null
      }
    }

    if (onSort) {
      onSort(nextKey, nextDir)
    } else {
      setLocalSortKey(nextKey)
      setLocalSortDir(nextDir)
    }
  }

  // --- Processamento Local: Ordenação ---
  const sortedData = useMemo(() => {
    if (onSort) return filteredData // Ordenação controlada por API externa

    if (!activeSortKey || !activeSortDir) return filteredData

    return [...filteredData].sort((a, b) => {
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
  }, [filteredData, activeSortKey, activeSortDir, onSort])

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
      <div
        className="w-full rounded-xl border border-border/60 overflow-hidden bg-card shadow-sm"
        role="status"
        aria-busy="true"
      >
        <span className="sr-only">Carregando registros...</span>
        <table className="w-full text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
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

      {/* --- Resumo dos Filtros Aplicados --- */}
      <AppliedFiltersBar
        appliedFilters={appliedFilters}
        onClear={handleFilterClear}
        onClearAll={handleClearAllFilters}
      />

      {/* Container de Rolagem Horizontal */}
      <div
        ref={scrollerRef}
        className="w-full overflow-x-auto scroller relative container-scroll-state"
      >
        {/* Sentinela de Borda Esquerda */}
        <div ref={leftSentinelRef} className="absolute left-0 top-0 w-px h-full pointer-events-none" />

        <table className="w-full text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr className="border-b border-border/60 bg-muted/40">
              {columns.map((col) => {
                const isSortable = col.sortable !== false && !!col.key
                const isCurrentlySorted = activeSortKey === col.key && !!activeSortDir
                const filterType = filterTypes[col.key]
                const columnFilterActive = !!filterType && isFilterActive(filterType, activeFilters[col.key])

                return (
                  <th
                    key={col.key}
                    scope="col"
                    className={cn(
                      "px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap",
                      col.className
                    )}
                    aria-sort={
                      isCurrentlySorted ? (activeSortDir === "asc" ? "ascending" : "descending") : undefined
                    }
                  >
                    <div className="flex items-center gap-1.5">
                      {isSortable ? (
                        // Botão nativo (em vez de onClick no <th>) dá suporte a teclado de graça
                        // e preserva a semântica de columnheader do <th>, que role="button" quebraria.
                        <button
                          type="button"
                          onClick={() => handleSortClick(col.key)}
                          className="flex items-center gap-1.5 -mx-1.5 -my-1 rounded px-1.5 py-1 select-none hover:bg-muted/60 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                        >
                          <span>{col.header}</span>
                          <span className="text-muted-foreground/60 transition-colors duration-150">
                            {isCurrentlySorted ? (
                              activeSortDir === "asc" ? (
                                <ChevronUp className="h-4 w-4 text-primary" aria-hidden="true" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-primary" aria-hidden="true" />
                              )
                            ) : (
                              <ArrowUpDown className="h-3.5 w-3.5 opacity-40 hover:opacity-100" aria-hidden="true" />
                            )}
                          </span>
                        </button>
                      ) : (
                        col.header
                      )}
                      {filterType && (
                        <button
                          type="button"
                          data-filter-trigger={col.key}
                          onClick={(e) => handleFilterToggle(e, col.key)}
                          aria-haspopup="dialog"
                          aria-expanded={openFilterKey === col.key}
                          aria-label={`Filtrar coluna ${typeof col.header === "string" ? col.header : col.key}`}
                          className={cn(
                            "ml-0.5 rounded p-1.5 transition-colors",
                            "hover:bg-muted focus:outline-none focus:ring-2 focus:ring-primary/40",
                            columnFilterActive || openFilterKey === col.key
                              ? "text-primary"
                              : "text-muted-foreground/40 hover:text-foreground"
                          )}
                        >
                          <Filter
                            className="h-3.5 w-3.5"
                            aria-hidden="true"
                            fill={columnFilterActive ? "currentColor" : "none"}
                          />
                        </button>
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
                  {appliedFilters.length > 0 ? (
                    <div className="flex flex-col items-center gap-2">
                      <span>Nenhum registro corresponde aos filtros aplicados.</span>
                      <button
                        type="button"
                        onClick={handleClearAllFilters}
                        className="text-xs font-semibold text-primary transition-opacity hover:opacity-80"
                      >
                        Limpar filtros
                      </button>
                    </div>
                  ) : (
                    emptyMessage
                  )}
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

      {/* --- Popover de Filtro da Coluna Ativa --- */}
      {openFilterKey && anchorRect && (
        <ColumnFilterPopover
          column={columns.find((col) => col.key === openFilterKey)}
          type={filterTypes[openFilterKey]}
          value={activeFilters[openFilterKey]}
          anchorRect={anchorRect}
          data={data}
          onChange={(value) => handleFilterValueChange(openFilterKey, value)}
          onClear={() => handleFilterClear(openFilterKey)}
          onClose={closeFilter}
        />
      )}

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

export { DataTable, AppliedFiltersBar, FilterToolbar }
