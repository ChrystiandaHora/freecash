/**
 * Testes da formatação monetária e da máscara de privacidade.
 *
 * A máscara tem comprimento fixo de propósito: se "R$ 12,00" virasse "R$ ••••" e
 * "R$ 1.234.567,00" virasse "R$ •••••••••", o número de pontos entregaria a ordem de
 * grandeza do patrimônio a quem olhasse a tela por cima do ombro.
 */
import { describe, expect, it } from 'vitest';

import { formatarMoeda, formatarMoedaCompacta, MASCARA_MOEDA } from './moeda';

// Intl usa espaço não separável entre "R$" e o número.
const semNbsp = (texto) => texto.replace(/\u00a0/g, ' ');

describe('formatarMoeda', () => {
  it('formata em reais por extenso quando não pede ocultação', () => {
    expect(semNbsp(formatarMoeda(1234.56))).toBe('R$ 1.234,56');
  });

  it('aceita string numérica vinda da API', () => {
    expect(semNbsp(formatarMoeda('99.9'))).toBe('R$ 99,90');
  });

  it('trata nulo e indefinido como zero', () => {
    expect(semNbsp(formatarMoeda(null))).toBe('R$ 0,00');
    expect(semNbsp(formatarMoeda(undefined))).toBe('R$ 0,00');
  });

  it('devolve a máscara quando ocultar está ligado', () => {
    expect(formatarMoeda(1234.56, { ocultar: true })).toBe(MASCARA_MOEDA);
  });

  it('não varia a máscara com a ordem de grandeza nem com o sinal', () => {
    const pequenos = formatarMoeda(3, { ocultar: true });
    const grandes = formatarMoeda(-9876543.21, { ocultar: true });
    expect(pequenos).toBe(grandes);
  });

  it('mantém o valor real com ocultar desligado', () => {
    expect(semNbsp(formatarMoeda(10, { ocultar: false }))).toBe('R$ 10,00');
  });
});

describe('formatarMoedaCompacta', () => {
  it('abrevia o valor quando não pede ocultação', () => {
    expect(semNbsp(formatarMoedaCompacta(1200))).toBe('R$ 1,2 mil');
  });

  it('usa a mesma máscara da forma completa', () => {
    expect(formatarMoedaCompacta(1200, { ocultar: true })).toBe(MASCARA_MOEDA);
  });
});
