/**
 * Teste tabelado da classificação de contas nas colunas do quadro.
 *
 * As bordas são de data, e todas silenciosas: uma conta que cai na coluna errada não
 * dá erro, só aparece no lugar errado — e "atrasada" exibida como "pendente" é a
 * informação que mais custa ao usuário nesta tela.
 *
 * Não precisa de jsdom nem de @testing-library — `lib/contasKanban.js` é puro.
 */
import { describe, expect, it } from 'vitest';
import { COLUMNS, agruparPorColuna, getColumnId } from './contasKanban';

/** Devolve 'YYYY-MM-DD' deslocado em `dias` a partir de hoje. */
const emDias = (dias) => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

describe('getColumnId', () => {
  /** [caso, conta, coluna esperada] */
  const CASOS = [
    ['paga vai para pagas mesmo estando vencida', { pago: true, data_vencimento: emDias(-30) }, 'pagas'],
    ['paga sem data também', { pago: true, data_vencimento: null }, 'pagas'],
    ['vencida ontem é atrasada', { pago: false, data_vencimento: emDias(-1) }, 'atrasadas'],
    ['vencida há meses é atrasada', { pago: false, data_vencimento: emDias(-90) }, 'atrasadas'],
    ['vence hoje não é atrasada', { pago: false, data_vencimento: emDias(0) }, 'hoje'],
    ['vence amanhã', { pago: false, data_vencimento: emDias(1) }, 'amanha'],
    ['vence em 2 dias', { pago: false, data_vencimento: emDias(2) }, 'vence_2_dias'],
    ['vence em 3 dias', { pago: false, data_vencimento: emDias(3) }, 'vence_3_dias'],
    ['vence em 4 dias cai no balde de pendentes', { pago: false, data_vencimento: emDias(4) }, 'pendentes'],
    ['sem data de vencimento fica em pendentes', { pago: false, data_vencimento: null }, 'pendentes'],
    ['data malformada não estoura', { pago: false, data_vencimento: '2026-09' }, 'pendentes'],
    ['data não-string não estoura', { pago: false, data_vencimento: 20260908 }, 'pendentes'],
    ['conta ausente não estoura', null, 'pendentes'],
  ];

  it.each(CASOS)('%s', (_caso, conta, esperado) => {
    expect(getColumnId(conta)).toBe(esperado);
  });

  it('só devolve ids que existem como coluna', () => {
    const ids = COLUMNS.map((c) => c.id);
    CASOS.forEach(([, conta]) => {
      expect(ids).toContain(getColumnId(conta));
    });
  });
});

describe('agruparPorColuna', () => {
  it('cria toda coluna, inclusive as vazias', () => {
    const mapa = agruparPorColuna([]);
    expect(Object.keys(mapa).sort()).toEqual(COLUMNS.map((c) => c.id).sort());
    COLUMNS.forEach((col) => expect(mapa[col.id]).toEqual([]));
  });

  it('distribui sem perder nem duplicar conta', () => {
    const contas = [
      { id: 1, pago: false, data_vencimento: emDias(-2) },
      { id: 2, pago: false, data_vencimento: emDias(0) },
      { id: 3, pago: true, data_vencimento: emDias(-5) },
      { id: 4, pago: false, data_vencimento: null },
    ];
    const mapa = agruparPorColuna(contas);

    const total = Object.values(mapa).reduce((n, lista) => n + lista.length, 0);
    expect(total).toBe(contas.length);
    expect(mapa.atrasadas.map((c) => c.id)).toEqual([1]);
    expect(mapa.hoje.map((c) => c.id)).toEqual([2]);
    expect(mapa.pagas.map((c) => c.id)).toEqual([3]);
    expect(mapa.pendentes.map((c) => c.id)).toEqual([4]);
  });

  it('sem argumento devolve as colunas vazias', () => {
    expect(agruparPorColuna()).toEqual(agruparPorColuna([]));
  });
});
