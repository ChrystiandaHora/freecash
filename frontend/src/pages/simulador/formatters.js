export const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0);

// Data por extenso: leitor de tela lê "26 de agosto de 2026" em vez de "26/08".
export const formatDateLong = (date) =>
  date.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' });
