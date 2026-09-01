/**
 * Utilitários de data ISO (AAAA-MM-DD) para filtros e API.
 * As conversões utilizam partes locais para evitar desvios de fuso horário (UTC).
 */

/** Nomes dos meses em português. */
export const NOMES_DOS_MESES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

/** Dias da semana (iniciando em domingo, padrão Date.getDay()). */
export const DIAS_DA_SEMANA = [
  { curto: 'D', longo: 'domingo' },
  { curto: 'S', longo: 'segunda-feira' },
  { curto: 'T', longo: 'terça-feira' },
  { curto: 'Q', longo: 'quarta-feira' },
  { curto: 'Q', longo: 'quinta-feira' },
  { curto: 'S', longo: 'sexta-feira' },
  { curto: 'S', longo: 'sábado' },
];

/** Converte Date para string ISO curta (AAAA-MM-DD) no fuso local. */
export function paraISO(data) {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, '0');
  const dia = String(data.getDate()).padStart(2, '0');
  return `${ano}-${mes}-${dia}`;
}

/** Converte string AAAA-MM-DD em Date no fuso local (meia-noite local). */
export function deISO(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  const data = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(data.getTime()) ? null : data;
}

/** Formata AAAA-MM-DD para exibição em pt-BR (dd/mm/aaaa). */
export function formatarData(iso) {
  const data = deISO(iso);
  return data ? data.toLocaleDateString('pt-BR') : '';
}

/** Comparação lexicográfica de datas ISO (dispensa construir Date). */
export function compararISO(a, b) {
  if (a === b) return 0;
  return a < b ? -1 : 1;
}

/** Monta matriz de semanas (7 colunas) para o calendário do mês. */
export function montarGradeDoMes(ano, mes) {
  const primeiro = new Date(ano, mes - 1, 1);
  const diasNoMes = new Date(ano, mes, 0).getDate();
  const deslocamento = primeiro.getDay();

  const celulas = [
    ...Array(deslocamento).fill(null),
    ...Array.from({ length: diasNoMes }, (_, i) => ({
      dia: i + 1,
      iso: paraISO(new Date(ano, mes - 1, i + 1)),
    })),
  ];

  while (celulas.length % 7 !== 0) celulas.push(null);

  const semanas = [];
  for (let i = 0; i < celulas.length; i += 7) {
    semanas.push(celulas.slice(i, i + 7));
  }
  return semanas;
}

/** Desloca ano/mês por delta relativo (positivo ou negativo). */
export function deslocarMes(ano, mes, delta) {
  const referencia = new Date(ano, mes - 1 + delta, 1);
  return { ano: referencia.getFullYear(), mes: referencia.getMonth() + 1 };
}

/** Retorna { from, to } cobrindo o primeiro e último dia do mês. */
export function intervaloDoMes(ano, mes) {
  const ultimoDia = new Date(ano, mes, 0).getDate();
  return {
    from: paraISO(new Date(ano, mes - 1, 1)),
    to: paraISO(new Date(ano, mes - 1, ultimoDia)),
  };
}

/** Atalhos dinâmicos de período para filtros. */

export const ATALHOS_DE_PERIODO = [
  {
    id: 'mes-atual',
    rotulo: 'Este mês',
    calcular: () => {
      const hoje = new Date();
      return intervaloDoMes(hoje.getFullYear(), hoje.getMonth() + 1);
    },
  },
  {
    id: 'mes-anterior',
    rotulo: 'Mês passado',
    calcular: () => {
      const hoje = new Date();
      const { ano, mes } = deslocarMes(hoje.getFullYear(), hoje.getMonth() + 1, -1);
      return intervaloDoMes(ano, mes);
    },
  },
  {
    id: 'mes-seguinte',
    rotulo: 'Próximo mês',
    calcular: () => {
      const hoje = new Date();
      const { ano, mes } = deslocarMes(hoje.getFullYear(), hoje.getMonth() + 1, 1);
      return intervaloDoMes(ano, mes);
    },
  },
  {
    id: 'ultimos-30',
    rotulo: 'Últimos 30 dias',
    calcular: () => {
      const hoje = new Date();
      const inicio = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - 29);
      return { from: paraISO(inicio), to: paraISO(hoje) };
    },
  },
  {
    id: 'proximos-30',
    rotulo: 'Próximos 30 dias',
    calcular: () => {
      const hoje = new Date();
      const fim = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() + 29);
      return { from: paraISO(hoje), to: paraISO(fim) };
    },
  },
  {
    id: 'ano-atual',
    rotulo: 'Este ano',
    calcular: () => {
      const ano = new Date().getFullYear();
      return { from: `${ano}-01-01`, to: `${ano}-12-31` };
    },
  },
];
