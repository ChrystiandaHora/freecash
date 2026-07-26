import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Retorna o intervalo de datas do mês atual (do 1º ao último dia) no formato ISO (YYYY-MM-DD).
 */
export function getCurrentMonthDateRange() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const lastDay = new Date(year, now.getMonth() + 1, 0).getDate()
  const lastDayStr = String(lastDay).padStart(2, '0')

  return {
    from: `${year}-${month}-01`,
    to: `${year}-${month}-${lastDayStr}`,
  }
}

