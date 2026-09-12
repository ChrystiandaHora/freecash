/**
 * Testes dos helpers de data do filtro de tabela.
 *
 * O que estes testes protegem é um bug que não aparece na tela: `new Date('2026-08-27')`
 * é interpretado como meia-noite **UTC**, e em UTC−3 isso vira 26/08 às 21h. Num
 * filtro de intervalo, esse deslocamento de um dia faz o primeiro ou o último dia
 * do período desaparecer da lista, sem erro e sem aviso. É o tipo de defeito que só
 * é notado quando alguém confere um total à mão.
 *
 * Por isso as conversões precisam ser sempre por partes locais, nunca por parse de
 * string ISO cru.
 */
import { describe, expect, it } from 'vitest';

import {
  ATALHOS_DE_PERIODO,
  compararISO,
  deISO,
  deslocarMes,
  formatarData,
  intervaloDoMes,
  montarGradeDoMes,
  paraISO,
} from './datas';

describe('conversão entre Date e ISO', () => {
  it('não desloca o dia ao converter ida e volta', () => {
    // Guarda o bug de fuso: com parse UTC, este caso voltaria como 26.
    expect(paraISO(deISO('2026-08-27'))).toBe('2026-08-27');
  });

  it('preserva o primeiro dia do mês', () => {
    expect(paraISO(deISO('2026-01-01'))).toBe('2026-01-01');
  });

  it('preserva o último dia do ano, onde o deslocamento viraria o ano', () => {
    expect(paraISO(deISO('2026-12-31'))).toBe('2026-12-31');
  });

  it('preenche mês e dia com zero à esquerda', () => {
    expect(paraISO(new Date(2026, 0, 5))).toBe('2026-01-05');
  });

  it('devolve nulo para entrada vazia ou inválida', () => {
    expect(deISO('')).toBeNull();
    expect(deISO(null)).toBeNull();
    expect(deISO('27/08/2026')).toBeNull();
  });

  it('formata para leitura em português', () => {
    expect(formatarData('2026-08-27')).toBe('27/08/2026');
    expect(formatarData('')).toBe('');
  });
});

describe('comparação de datas ISO', () => {
  it('ordena cronologicamente', () => {
    expect(compararISO('2026-08-01', '2026-08-27')).toBeLessThan(0);
    expect(compararISO('2026-09-01', '2026-08-27')).toBeGreaterThan(0);
    expect(compararISO('2026-08-27', '2026-08-27')).toBe(0);
  });

  it('ordena corretamente na virada de ano', () => {
    expect(compararISO('2026-12-31', '2027-01-01')).toBeLessThan(0);
  });
});

describe('grade do mês', () => {
  it('produz semanas de sete posições', () => {
    for (const semana of montarGradeDoMes(2026, 8)) {
      expect(semana).toHaveLength(7);
    }
  });

  it('cobre todos os dias do mês, sem repetir nem faltar', () => {
    const dias = montarGradeDoMes(2026, 8)
      .flat()
      .filter(Boolean)
      .map((c) => c.dia);

    expect(dias).toHaveLength(31);
    expect(dias[0]).toBe(1);
    expect(dias[30]).toBe(31);
  });

  it('respeita fevereiro em ano comum e em bissexto', () => {
    const comum = montarGradeDoMes(2026, 2).flat().filter(Boolean);
    const bissexto = montarGradeDoMes(2028, 2).flat().filter(Boolean);

    expect(comum).toHaveLength(28);
    expect(bissexto).toHaveLength(29);
  });

  it('alinha o primeiro dia na coluna do dia da semana correto', () => {
    // 1º de agosto de 2026 é sábado; domingo = 0, então sábado = índice 6.
    const primeiraSemana = montarGradeDoMes(2026, 8)[0];
    expect(primeiraSemana.slice(0, 6).every((c) => c === null)).toBe(true);
    expect(primeiraSemana[6].dia).toBe(1);
  });

  it('gera o ISO de cada célula sem deslocamento', () => {
    const primeiro = montarGradeDoMes(2026, 8).flat().filter(Boolean)[0];
    expect(primeiro.iso).toBe('2026-08-01');
  });
});

describe('deslocamento de mês', () => {
  it('avança dentro do ano', () => {
    expect(deslocarMes(2026, 8, 1)).toEqual({ ano: 2026, mes: 9 });
  });

  it('vira o ano para frente', () => {
    expect(deslocarMes(2026, 12, 1)).toEqual({ ano: 2027, mes: 1 });
  });

  it('vira o ano para trás', () => {
    expect(deslocarMes(2026, 1, -1)).toEqual({ ano: 2025, mes: 12 });
  });
});

describe('intervalo do mês', () => {
  it('vai do primeiro ao último dia', () => {
    expect(intervaloDoMes(2026, 8)).toEqual({
      from: '2026-08-01',
      to: '2026-08-31',
    });
  });

  it('acerta o último dia de fevereiro bissexto', () => {
    expect(intervaloDoMes(2028, 2).to).toBe('2028-02-29');
  });

  it('acerta meses de 30 dias', () => {
    expect(intervaloDoMes(2026, 9).to).toBe('2026-09-30');
  });
});

describe('atalhos de período', () => {
  it('todos devolvem um intervalo com início não posterior ao fim', () => {
    for (const atalho of ATALHOS_DE_PERIODO) {
      const { from, to } = atalho.calcular();
      expect(from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(compararISO(from, to)).toBeLessThanOrEqual(0);
    }
  });

  it('são funções, e não valores fixos', () => {
    // Um valor calculado na importação do módulo ficaria errado numa aba deixada
    // aberta pela virada do mês.
    for (const atalho of ATALHOS_DE_PERIODO) {
      expect(typeof atalho.calcular).toBe('function');
    }
  });

  it('"últimos 30 dias" termina hoje e cobre 30 dias', () => {
    const { from, to } = ATALHOS_DE_PERIODO.find((a) => a.id === 'ultimos-30').calcular();
    expect(to).toBe(paraISO(new Date()));

    const dias = Math.round((deISO(to) - deISO(from)) / 86400000) + 1;
    expect(dias).toBe(30);
  });

  it('"este mês" cobre o mês corrente inteiro', () => {
    const hoje = new Date();
    expect(ATALHOS_DE_PERIODO.find((a) => a.id === 'mes-atual').calcular()).toEqual(
      intervaloDoMes(hoje.getFullYear(), hoje.getMonth() + 1)
    );
  });
});
