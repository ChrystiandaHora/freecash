/**
 * Testes do filtro da tabela de despesas do evento.
 *
 * O `resumo` do evento serializa a conta com `ContasPagarAPISerializer`, que manda o
 * nome da categoria em `categoria`. A tela lia `categoria_nome`, campo que não
 * existe: a coluna mostrava "—" e o filtro nunca casava pela categoria.
 *
 * Não precisa de jsdom nem de @testing-library — `lib/lancamentosEvento.js` é puro.
 */
import { describe, expect, it } from 'vitest';
import { filtrarLancamentos, nomeCategoria } from './lancamentosEvento';

const LAPTOP = { id: 1, descricao: 'Laptop novo (equipamento da empresa)', categoria: 'Investimento' };
const POUSADA = { id: 2, descricao: 'Pousada Maragogi', categoria: 'Viagem' };
const SEM_CATEGORIA = { id: 3, descricao: 'Taxa avulsa', categoria: null };
const LANCAMENTOS = [LAPTOP, POUSADA, SEM_CATEGORIA];

describe('nomeCategoria', () => {
  it('lê o nome que o resumo manda em `categoria`', () => {
    expect(nomeCategoria(LAPTOP)).toBe('Investimento');
  });

  it('mostra travessão quando a conta não tem categoria', () => {
    expect(nomeCategoria(SEM_CATEGORIA)).toBe('—');
  });
});

describe('filtrarLancamentos', () => {
  it('devolve tudo quando a busca está vazia ou só com espaços', () => {
    expect(filtrarLancamentos(LANCAMENTOS, '')).toEqual(LANCAMENTOS);
    expect(filtrarLancamentos(LANCAMENTOS, '   ')).toEqual(LANCAMENTOS);
  });

  it('casa pela descrição, sem diferenciar maiúsculas', () => {
    expect(filtrarLancamentos(LANCAMENTOS, 'LAPTOP')).toEqual([LAPTOP]);
  });

  it('casa pelo nome da categoria', () => {
    expect(filtrarLancamentos(LANCAMENTOS, 'viag')).toEqual([POUSADA]);
  });

  it('não quebra com conta sem categoria', () => {
    expect(filtrarLancamentos(LANCAMENTOS, 'taxa')).toEqual([SEM_CATEGORIA]);
  });
});
