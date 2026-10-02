/**
 * Regras de filtragem por coluna do DataTable, puras e sem React.
 *
 * Ficam fora do componente para que outra visão dos mesmos dados (ex.: o kanban
 * de Contas a Pagar) aplique exatamente o filtro da tabela sem precisar montá-la.
 */

/** Normaliza texto removendo acentos e caixa, para comparações tolerantes em pt-BR. */
const normalizeText = (val) =>
  String(val ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()

/** Converte um valor arbitrário em data ISO (YYYY-MM-DD) ou null caso não seja temporal. */
const toISODate = (val) => {
  if (val === null || val === undefined || val === "") return null
  if (val instanceof Date) {
    return Number.isNaN(val.getTime()) ? null : val.toISOString().slice(0, 10)
  }
  const str = String(val)
  const isoMatch = str.match(/^(\d{4}-\d{2}-\d{2})/)
  if (isoMatch) return isoMatch[1]

  // Suporte a datas no formato brasileiro (DD/MM/YYYY)
  const brMatch = str.match(/^(\d{2})\/(\d{2})\/(\d{4})/)
  if (brMatch) return `${brMatch[3]}-${brMatch[2]}-${brMatch[1]}`

  const parsed = new Date(str)
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10)
}

/** Extrai o valor bruto de uma coluna usado na filtragem (permite acessor customizado). */
const getFilterValue = (col, row) =>
  col.filterAccessor ? col.filterAccessor(row) : row[col.key]

/** Verifica se um valor está preenchido (tratando 0 e false como preenchidos). */
const hasValue = (val) => val !== "" && val !== null && val !== undefined

/**
 * Infere o tipo de filtro de uma coluna a partir da primeira amostra de dados,
 * salvo quando o tipo é declarado explicitamente via `col.filterType`.
 */
const inferFilterType = (col, data) => {
  if (col.filterType) return col.filterType
  if (col.filterOptions) return "select"

  const sampleRow = data.find((row) => hasValue(getFilterValue(col, row)))
  if (!sampleRow) return "text"

  const sample = getFilterValue(col, sampleRow)
  if (typeof sample === "boolean") return "boolean"
  if (sample instanceof Date) return "date"
  if (typeof sample === "string" && /^\d{4}-\d{2}-\d{2}/.test(sample)) return "date"
  if (typeof sample === "number") return "number"
  // Valores decimais serializados como string pela API (ex.: "1500.00")
  if (typeof sample === "string" && sample.trim() !== "" && !Number.isNaN(Number(sample))) return "number"
  return "text"
}

/** Indica se o filtro de uma coluna possui algum critério ativo. */
const isFilterActive = (type, value) => {
  if (!hasValue(value)) return false
  if (type === "date") return hasValue(value.from) || hasValue(value.to)
  if (type === "number") return hasValue(value.min) || hasValue(value.max)
  return true
}

/** Aplica o critério de filtro de uma coluna sobre uma linha. */
const matchesFilter = (col, type, row, filterValue) => {
  if (!isFilterActive(type, filterValue)) return true
  const raw = getFilterValue(col, row)

  if (type === "date") {
    const iso = toISODate(raw)
    if (!iso) return false
    if (hasValue(filterValue.from) && iso < filterValue.from) return false
    if (hasValue(filterValue.to) && iso > filterValue.to) return false
    return true
  }

  if (type === "number") {
    const num = Number(raw)
    if (Number.isNaN(num)) return false
    if (hasValue(filterValue.min) && num < Number(filterValue.min)) return false
    if (hasValue(filterValue.max) && num > Number(filterValue.max)) return false
    return true
  }

  if (type === "boolean") {
    const isTruthy = raw === true || raw === "true" || raw === 1
    return filterValue === "true" ? isTruthy : !isTruthy
  }

  if (type === "select") {
    return String(raw ?? "") === String(filterValue)
  }

  return normalizeText(raw).includes(normalizeText(filterValue))
}

/** Descreve o filtro ativo em texto curto, usado nos chips de resumo. */
const describeFilter = (type, value) => {
  if (type === "date") {
    const from = hasValue(value.from) ? toISODate(value.from) : null
    const to = hasValue(value.to) ? toISODate(value.to) : null
    const fmt = (iso) => iso.split("-").reverse().join("/")
    if (from && to) return `${fmt(from)} — ${fmt(to)}`
    if (from) return `a partir de ${fmt(from)}`
    return `até ${fmt(to)}`
  }
  if (type === "number") {
    if (hasValue(value.min) && hasValue(value.max)) return `${value.min} — ${value.max}`
    if (hasValue(value.min)) return `≥ ${value.min}`
    return `≤ ${value.max}`
  }
  if (type === "boolean") return value === "true" ? "Sim" : "Não"
  return String(value)
}

/** Mapeia cada coluna filtrável ao seu tipo de filtro. */
const resolveFilterTypes = (columns, data, filterable = true) => {
  if (!filterable) return {}
  return columns.reduce((acc, col) => {
    // Colunas não ordenáveis (ex.: ações) ficam fora por padrão, salvo opt-in explícito
    const enabled =
      col.filterable === true || (col.filterable !== false && col.sortable !== false)

    if (col.key && enabled) {
      acc[col.key] = inferFilterType(col, data)
    }
    return acc
  }, {})
}

/**
 * Aplica os filtros por coluna sobre as linhas, com as mesmas regras da tabela.
 * Exportado para que outra visão dos mesmos dados (ex.: um kanban) respeite o
 * filtro da tabela sem precisar montá-la.
 */
const applyColumnFilters = (columns, data, filters, filterTypes = resolveFilterTypes(columns, data)) => {
  const entries = Object.entries(filters || {}).filter(
    ([key, value]) => filterTypes[key] && isFilterActive(filterTypes[key], value)
  )
  if (entries.length === 0) return data

  const columnByKey = new Map(columns.map((col) => [col.key, col]))
  return data.filter((row) =>
    entries.every(([key, value]) => matchesFilter(columnByKey.get(key), filterTypes[key], row, value))
  )
}

/** Lista as colunas com filtro ativo e o rótulo curto de cada critério. */
const describeAppliedFilters = (columns, filters, filterTypes) =>
  columns
    .filter((col) => filterTypes[col.key] && isFilterActive(filterTypes[col.key], filters?.[col.key]))
    .map((col) => ({
      col,
      type: filterTypes[col.key],
      label: describeFilter(filterTypes[col.key], filters[col.key]),
    }))

export {
  normalizeText,
  toISODate,
  getFilterValue,
  hasValue,
  inferFilterType,
  isFilterActive,
  matchesFilter,
  describeFilter,
  resolveFilterTypes,
  applyColumnFilters,
  describeAppliedFilters,
}
