import { describe, expect, it } from 'vitest';

import { montarLinhaDoTempo, rotuloMes } from './linhaDoTempoSaldo';

const mes = (ano, numero, extra = {}) => ({
  ano,
  mes: numero,
  total_receitas: '100.00',
  total_despesas: '40.00',
  aporte_metas: '10.00',
  saldo_abertura: '0',
  saldo_abertura_com_metas: '0',
  saldo_final: '60.00',
  saldo_final_com_metas: '50.00',
  ...extra,
});

const resposta = {
  inicio: '2026-10-09',
  saldo_inicial: '38649.55',
  historico: [
    { ano: 2026, mes: 9, receitas: '10.00', despesas: '0.00', saldo_final: '52000.00', parcial: false },
    { ano: 2026, mes: 10, receitas: '541.55', despesas: '0.00', saldo_final: '52541.55', parcial: true },
  ],
  meses: [mes(2026, 10), mes(2026, 11)],
};

describe('rotuloMes', () => {
  it('abrevia o mês em português, sem ponto', () => {
    expect(rotuloMes(2026, 10)).toBe('out/26');
  });
});

describe('montarLinhaDoTempo', () => {
  it('ordena passado, abertura de hoje e projeção', () => {
    const pontos = montarLinhaDoTempo(resposta, false);
    expect(pontos.map((p) => p.tipo)).toEqual([
      'realizado', 'realizado', 'abertura', 'projetado', 'projetado',
    ]);
  });

  it('termina o passado no caixa de ontem e marca o mês parcial', () => {
    const pontos = montarLinhaDoTempo(resposta, false);
    expect(pontos[1].saldo).toBe(52541.55);
    expect(pontos[1].rotulo).toBe('out/26 até 08/10');
  });

  it('a abertura é o saldo inicial da projeção', () => {
    const abertura = montarLinhaDoTempo(resposta, false).find((p) => p.tipo === 'abertura');
    expect(abertura.saldo).toBe(38649.55);
  });

  it('o cenário de metas troca os saldos e inclui o aporte', () => {
    const [semMetas, comMetas] = [false, true].map(
      (metas) => montarLinhaDoTempo(resposta, metas).find((p) => p.tipo === 'projetado'),
    );
    expect([semMetas.saldo, semMetas.aporte]).toEqual([60, 0]);
    expect([comMetas.saldo, comMetas.aporte]).toEqual([50, 10]);
  });

  it('sem histórico, começa direto na abertura', () => {
    const pontos = montarLinhaDoTempo({ ...resposta, historico: [] }, false);
    expect(pontos[0].tipo).toBe('abertura');
  });
});
