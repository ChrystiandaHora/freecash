/**
 * Testes dos textos e da leitura dos sinais de rebalanceamento.
 *
 * O formatador de moeda é injetado, então aqui ele é uma função simples: o que se testa
 * é a frase, não a máscara do olho de privacidade.
 */
import { describe, expect, it } from 'vitest';
import {
  apresentarSinal,
  sinaisPorAtivo,
  suspendeAporte,
  textoAcao,
  textoIsencao,
} from './sinais';

const moeda = (valor) => `R$${valor}`;

const VENDA_COM_LUCRO = {
  ativo_id: 1,
  tipo: 'VENDER_COM_LUCRO',
  queda_relevante: false,
  meta_porcentagem: 20,
  variacao_preco_medio: 25,
  cotas_a_vender: 100,
  valor_venda: 10000,
  resultado_venda: 2000,
  isencao: 'ISENTA',
  cotas_dentro_isencao: null,
};

describe('apresentarSinal', () => {
  it.each([
    ['VENDER_COM_LUCRO', 'Rebalancear com lucro', 'success'],
    ['VENDER_COM_PREJUIZO', 'Rebalancear com prejuízo', 'warning'],
    ['REVISAR_QUEDA', 'Revisar queda', 'destructive'],
  ])('%s vira o rótulo «%s»', (tipo, rotulo, variante) => {
    expect(apresentarSinal({ tipo })).toEqual({ rotulo, variante });
  });

  it('sem sinal não tem apresentação', () => {
    expect(apresentarSinal({ tipo: 'SEM_SINAL' })).toBeNull();
    expect(apresentarSinal(undefined)).toBeNull();
  });
});

describe('textoAcao', () => {
  it('venda com lucro diz quantas cotas, o valor e o lucro', () => {
    expect(textoAcao(VENDA_COM_LUCRO, moeda)).toBe(
      'Vender 100 cotas (R$10000) para voltar à meta de 20% realiza lucro de R$2000.'
    );
  });

  it('venda com prejuízo lembra que ele abate lucros futuros', () => {
    const sinal = { ...VENDA_COM_LUCRO, tipo: 'VENDER_COM_PREJUIZO', resultado_venda: -500 };

    expect(textoAcao(sinal, moeda)).toBe(
      'Vender 100 cotas (R$10000) para voltar à meta de 20% realiza prejuízo de R$500, ' +
        'que pode abater lucros futuros do mesmo tipo de ativo.'
    );
  });

  it('uma cota fica no singular', () => {
    expect(textoAcao({ ...VENDA_COM_LUCRO, cotas_a_vender: 1 }, moeda)).toMatch(/^Vender 1 cota \(/);
  });

  it('queda relevante pede revisão, não venda', () => {
    const sinal = { tipo: 'REVISAR_QUEDA', queda_relevante: true, variacao_preco_medio: -23.456 };

    expect(textoAcao(sinal, moeda)).toBe(
      'Caiu 23,5% desde o seu preço médio. Revise o motivo de ter este ativo antes de reforçar ou vender.'
    );
  });

  it('venda com queda relevante acrescenta o aviso de queda', () => {
    const sinal = {
      ...VENDA_COM_LUCRO,
      tipo: 'VENDER_COM_PREJUIZO',
      resultado_venda: -3000,
      queda_relevante: true,
      variacao_preco_medio: -30,
    };

    expect(textoAcao(sinal, moeda)).toMatch(/Caiu 30,0% desde o seu preço médio\.$/);
  });
});

describe('textoIsencao', () => {
  it('venda que cabe na isenção', () => {
    expect(textoIsencao(VENDA_COM_LUCRO)).toBe(
      'Cabe na isenção de R$ 20 mil em vendas de ações no mês.'
    );
  });

  it('venda que estoura a isenção diz quantas cotas cabem', () => {
    const sinal = { ...VENDA_COM_LUCRO, isencao: 'EXCEDE', cotas_dentro_isencao: 50 };

    expect(textoIsencao(sinal)).toBe(
      'Passa de R$ 20 mil em vendas de ações no mês. Até 50 cotas cabem na isenção agora; ' +
        'o restante pode ficar para o mês que vem.'
    );
  });

  it('mês que já passou do limite', () => {
    const sinal = { ...VENDA_COM_LUCRO, isencao: 'EXCEDE', cotas_dentro_isencao: 0 };

    expect(textoIsencao(sinal)).toBe(
      'As vendas de ações deste mês já passaram de R$ 20 mil: o lucro do mês é tributável.'
    );
  });

  it('tipo sem isenção', () => {
    expect(textoIsencao({ ...VENDA_COM_LUCRO, isencao: 'TRIBUTAVEL' })).toBe(
      'Este tipo de ativo não tem a isenção de R$ 20 mil: o lucro é tributável.'
    );
  });

  it('sem venda não há texto', () => {
    expect(textoIsencao({ tipo: 'REVISAR_QUEDA', isencao: 'NAO_SE_APLICA' })).toBeNull();
  });
});

describe('suspendeAporte', () => {
  it('só a queda relevante suspende o aporte', () => {
    expect(suspendeAporte({ queda_relevante: true })).toBe(true);
    expect(suspendeAporte(VENDA_COM_LUCRO)).toBe(false);
    expect(suspendeAporte(undefined)).toBe(false);
  });
});

describe('sinaisPorAtivo', () => {
  it('agrupa os sinais do mesmo ativo em carteiras diferentes', () => {
    const porAtivo = sinaisPorAtivo([
      { ...VENDA_COM_LUCRO, carteira_id: 1 },
      { ...VENDA_COM_LUCRO, carteira_id: 2 },
      { ...VENDA_COM_LUCRO, ativo_id: 7, carteira_id: 1 },
    ]);

    expect(porAtivo.get(1)).toHaveLength(2);
    expect(porAtivo.get(7)).toHaveLength(1);
    expect(porAtivo.get(99)).toBeUndefined();
  });
});
