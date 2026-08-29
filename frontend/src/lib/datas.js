/**
 * Helpers de data no formato ISO curto (`AAAA-MM-DD`), que é o formato usado pelos
 * filtros das tabelas e pela API.
 *
 * **Todas as conversões são locais, nunca UTC.** `new Date('2026-08-27')` é
 * interpretado como meia-noite **UTC**; em UTC−3 isso vira 26/08 às 21h, e
 * `getDate()` devolve 26. Num filtro de data, esse deslocamento de um dia some da
 * tela sem deixar rastro — o intervalo simplesmente exclui o primeiro ou o último
 * dia. Por isso as datas aqui são montadas e lidas por partes explícitas, e o parse
 * segue a convenção que o projeto já usa: sufixo `T00:00:00`.
 *
 * @module lib/datas
 */

/** Nomes de mês em português, para o cabeçalho do calendário. */
export const NOMES_DOS_MESES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

/**
 * Dias da semana começando em domingo, que é a convenção de `Date.getDay()`.
 *
 * O calendário do FreeCash começa no domingo para casar com o calendário de
 * parede brasileiro, ao contrário do `Calendário de Pagamentos`, que monta a grade
 * a partir de dados vindos do Python (segunda = 0).
 */
export const DIAS_DA_SEMANA = [
  { curto: 'D', longo: 'domingo' },
  { curto: 'S', longo: 'segunda-feira' },
  { curto: 'T', longo: 'terça-feira' },
  { curto: 'Q', longo: 'quarta-feira' },
  { curto: 'Q', longo: 'quinta-feira' },
  { curto: 'S', longo: 'sexta-feira' },
  { curto: 'S', longo: 'sábado' },
];

/**
 * Converte um `Date` para `AAAA-MM-DD` usando as partes locais.
 *
 * @param {Date} data - Data a converter.
 * @returns {string} Data em ISO curto.
 */
export function paraISO(data) {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, '0');
  const dia = String(data.getDate()).padStart(2, '0');
  return `${ano}-${mes}-${dia}`;
}

/**
 * Converte `AAAA-MM-DD` em `Date` no fuso local.
 *
 * @param {string} iso - Data em ISO curto.
 * @returns {Date | null} Data local, ou null se a entrada for vazia ou inválida.
 */
export function deISO(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  const data = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(data.getTime()) ? null : data;
}

/**
 * Formata `AAAA-MM-DD` para leitura em português.
 *
 * @param {string} iso - Data em ISO curto.
 * @returns {string} Data no formato dd/mm/aaaa, ou string vazia se inválida.
 */
export function formatarData(iso) {
  const data = deISO(iso);
  return data ? data.toLocaleDateString('pt-BR') : '';
}

/**
 * Compara duas datas ISO curtas.
 *
 * A comparação é lexicográfica, e isso é seguro **porque** o formato é
 * `AAAA-MM-DD` com zeros à esquerda: a ordem alfabética coincide com a
 * cronológica. Evita construir objetos `Date` só para comparar.
 *
 * @param {string} a - Primeira data.
 * @param {string} b - Segunda data.
 * @returns {number} Negativo se `a` < `b`, zero se iguais, positivo se `a` > `b`.
 */
export function compararISO(a, b) {
  if (a === b) return 0;
  return a < b ? -1 : 1;
}

/**
 * Monta a grade de um mês em semanas de sete posições.
 *
 * As bordas são preenchidas com `null`, para que a tabela do calendário tenha
 * sempre sete colunas por linha.
 *
 * @param {number} ano - Ano de referência.
 * @param {number} mes - Mês de referência, de 1 a 12.
 * @returns {Array<Array<{dia: number, iso: string} | null>>} Semanas do mês.
 */
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

/**
 * Desloca um par ano/mês em N meses, normalizando a virada de ano.
 *
 * @param {number} ano - Ano de partida.
 * @param {number} mes - Mês de partida, de 1 a 12.
 * @param {number} delta - Quantidade de meses a somar (pode ser negativa).
 * @returns {{ano: number, mes: number}} Novo par ano/mês.
 */
export function deslocarMes(ano, mes, delta) {
  const referencia = new Date(ano, mes - 1 + delta, 1);
  return { ano: referencia.getFullYear(), mes: referencia.getMonth() + 1 };
}

/**
 * Devolve o intervalo completo de um mês.
 *
 * @param {number} ano - Ano de referência.
 * @param {number} mes - Mês de referência, de 1 a 12.
 * @returns {{from: string, to: string}} Primeiro e último dia do mês.
 */
export function intervaloDoMes(ano, mes) {
  const ultimoDia = new Date(ano, mes, 0).getDate();
  return {
    from: paraISO(new Date(ano, mes - 1, 1)),
    to: paraISO(new Date(ano, mes - 1, ultimoDia)),
  };
}

/**
 * Atalhos de período oferecidos pelo calendário de filtro.
 *
 * São funções, e não valores fixos, porque "este mês" precisa ser resolvido no
 * momento do clique — um valor calculado na importação do módulo ficaria errado
 * numa aba deixada aberta pela virada do mês.
 */
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
