/**
 * Testes das sugestões de categoria dos formulários de receita e despesa.
 *
 * `/api/categorias/` devolve todas as categorias do usuário, de todos os tipos; o
 * formulário só deve sugerir as do tipo do lançamento.
 */
import { describe, expect, it } from 'vitest';
import { nomesCategoriasPorTipo, opcoesCategoria } from './categorias';

const CATEGORIAS = [
  { id: 1, nome: 'Salário', tipo: 'R' },
  { id: 2, nome: 'Mercado', tipo: 'D' },
  { id: 3, nome: 'Investimento', tipo: 'I' },
  { id: 4, nome: 'Alimentação fora', tipo: 'D' },
  { id: 5, nome: 'Educação', tipo: 'D' },
];

describe('nomesCategoriasPorTipo', () => {
  it('devolve só os nomes do tipo pedido', () => {
    expect(nomesCategoriasPorTipo(CATEGORIAS, 'R')).toEqual(['Salário']);
  });

  it('ordena em ordem alfabética respeitando acentos', () => {
    expect(nomesCategoriasPorTipo(CATEGORIAS, 'D')).toEqual([
      'Alimentação fora',
      'Educação',
      'Mercado',
    ]);
  });

  it('devolve lista vazia enquanto as categorias não chegaram', () => {
    expect(nomesCategoriasPorTipo(undefined, 'D')).toEqual([]);
  });
});

describe('opcoesCategoria', () => {
  it('são os nomes do tipo quando o valor atual está entre eles', () => {
    expect(opcoesCategoria(CATEGORIAS, 'R', 'Salário')).toEqual(['Salário']);
  });

  it('inclui o valor atual de outro tipo, para a edição não mostrar o select vazio', () => {
    expect(opcoesCategoria(CATEGORIAS, 'D', 'Investimento')).toEqual([
      'Alimentação fora',
      'Educação',
      'Investimento',
      'Mercado',
    ]);
  });

  it('inclui o valor atual antes de a lista chegar do servidor', () => {
    expect(opcoesCategoria(undefined, 'D', 'Mercado')).toEqual(['Mercado']);
  });

  it('ignora valor vazio', () => {
    expect(opcoesCategoria(CATEGORIAS, 'R', '')).toEqual(['Salário']);
  });
});
