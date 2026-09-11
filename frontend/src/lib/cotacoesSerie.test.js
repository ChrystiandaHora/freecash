/**
 * Testes do preparo das séries do gráfico de cotações.
 *
 * Dois casos justificam o arquivo.
 *
 * `o último ponto do retorno é o número da coluna Retorno da tabela`: a coluna sai do
 * backend por uma conta, e a linha do gráfico por outra. Enquanto as duas baterem, o
 * gráfico é a leitura visual da tabela; no dia em que divergirem, o usuário vê dois
 * números diferentes para a mesma pergunta.
 *
 * `alinharEmEixoComum`: o tooltip compartilhado do ApexCharts casa séries por índice
 * do ponto. Com séries de comprimentos diferentes o ponteiro mostrava a data de uma
 * série com o valor de outra — foi o defeito relatado.
 *
 * `lib/cotacoesSerie.js` é puro — sem jsdom nem @testing-library.
 */
import { describe, expect, it } from 'vitest';
import { alinharEmEixoComum, converterPonto, converterSeries } from './cotacoesSerie';

/** Como o backend calcula `rentabilidade_percentual` (ver Ativo.rentabilidade_percentual). */
const retornoDoBackend = (quantidade, precoMedio, cotacaoAtual) => {
  const investido = quantidade * precoMedio;
  const atual = quantidade * cotacaoAtual;
  return ((atual - investido) / investido) * 100;
};

const serieDe = (id, ticker, pontos) => ({
  id,
  ticker,
  pontos: Object.entries(pontos).map(([data, valor]) => ({ data, valor })),
});

const listagem = (entradas) =>
  new Map(
    entradas.map(([id, precoMedio, retorno = '0']) => [
      id,
      { preco_medio: String(precoMedio), rentabilidade_percentual: String(retorno) },
    ])
  );

describe('converterPonto', () => {
  /** [caso, escala, valor, precoMedio, esperado] */
  const CASOS = [
    ['preço passa reto, sem rebase', 'preco', 30, 20, 30],
    ['retorno mede contra o preço médio', 'retorno', 30, 20, 50],
    ['retorno negativo abaixo do preço médio', 'retorno', 15, 20, -25],
    ['retorno zero exatamente no preço médio', 'retorno', 20, 20, 0],
    ['preço em reais funciona sem preço médio', 'preco', 30, 0, 30],
  ];

  it.each(CASOS)('%s', (_caso, escala, valor, precoMedio, esperado) => {
    expect(converterPonto(valor, escala, precoMedio)).toBe(esperado);
  });

  it('sem preço médio devolve null no retorno, e não zero', () => {
    // Zero seria lido como "empatado com o custo", que é diferente de "não se aplica"
    expect(converterPonto(30, 'retorno', 0)).toBeNull();
  });
});

describe('converterSeries', () => {
  it('o último ponto do retorno é o número da coluna Retorno da tabela', () => {
    const quantidade = 137.5;
    const precoMedio = 28.4321;
    const cotacaoAtual = 41.07;

    const [serie] = converterSeries(
      [serieDe(1, 'PETR4', { '2026-07-01': 30.0, '2026-07-02': 35.5, '2026-07-03': cotacaoAtual })],
      'retorno',
      listagem([[1, precoMedio]])
    );

    const daTabela = retornoDoBackend(quantidade, precoMedio, cotacaoAtual);
    // O gráfico arredonda em 2 casas para plotar; a igualdade vale nessa precisão
    expect(serie.pontos.at(-1).plotado).toBe(Number(daTabela.toFixed(2)));
  });

  it('lê preço médio e retorno da listagem, que é o que a tabela exibe', () => {
    const [serie] = converterSeries(
      [serieDe(7, 'HGLG11', { '2026-07-01': 10, '2026-07-02': 12 })],
      'retorno',
      listagem([[7, 10, '20.00']])
    );

    expect(serie.retornoAtual).toBe(20);
    expect(serie.pontos.map((p) => p.plotado)).toEqual([0, 20]);
  });

  it('descarta do retorno o ativo sem preço médio', () => {
    const convertidas = converterSeries(
      [
        serieDe(1, 'PETR4', { '2026-07-01': 30, '2026-07-02': 33 }),
        serieDe(2, 'ZERADO3', { '2026-07-01': 5, '2026-07-02': 6 }),
      ],
      'retorno',
      listagem([[1, 30, '10'], [2, 0]])
    );

    expect(convertidas.map((s) => s.ticker)).toEqual(['PETR4']);
  });

  it('em reais o ativo sem preço médio continua no gráfico', () => {
    const entrada = [serieDe(2, 'ZERADO3', { '2026-07-01': 5, '2026-07-02': 6 })];
    expect(converterSeries(entrada, 'preco', listagem([[2, 0]]))).toHaveLength(1);
  });

  it('ativo ausente da listagem não quebra a conversão', () => {
    // A série vem de uma query própria: pode chegar antes da listagem no primeiro render
    const entrada = [serieDe(9, 'ORFAO3', { '2026-07-01': 10, '2026-07-02': 11 })];
    expect(converterSeries(entrada, 'retorno', new Map())).toEqual([]);
    expect(converterSeries(entrada, 'preco', new Map())).toHaveLength(1);
  });
});

describe('alinharEmEixoComum', () => {
  it('põe séries de pregões diferentes na mesma grade de datas', () => {
    const { datas, series } = alinharEmEixoComum([
      { ticker: 'ANTIGO3', pontos: [
        { data: '2026-07-01', plotado: 1 },
        { data: '2026-07-02', plotado: 2 },
        { data: '2026-07-03', plotado: 3 },
      ] },
      { ticker: 'NOVO3', pontos: [{ data: '2026-07-03', plotado: 30 }] },
    ]);

    expect(datas).toEqual(['2026-07-01', '2026-07-02', '2026-07-03']);
    // Sem isto o tooltip casaria o único ponto do NOVO3 com o dia 01 do ANTIGO3
    expect(series[1].valores).toEqual([null, null, 30]);
    expect(series[0].valores).toEqual([1, 2, 3]);
  });

  it('todas as séries saem com o mesmo comprimento, que é o do eixo', () => {
    const { datas, series } = alinharEmEixoComum([
      { ticker: 'A', pontos: [{ data: '2026-07-01', plotado: 1 }] },
      { ticker: 'B', pontos: [{ data: '2026-07-05', plotado: 5 }] },
      { ticker: 'C', pontos: [{ data: '2026-07-03', plotado: 3 }] },
    ]);

    expect(datas).toEqual(['2026-07-01', '2026-07-03', '2026-07-05']);
    series.forEach((s) => expect(s.valores).toHaveLength(datas.length));
  });

  it('pregão faltando no meio repete o último fechamento conhecido', () => {
    // Fundos que só recebem cotação quando o coletor roda ficam sem metade da grade;
    // uma linha quebrada em vinte pedaços não se lê (ver a docstring da função).
    const { series } = alinharEmEixoComum([
      { ticker: 'A', pontos: [
        { data: '2026-07-01', plotado: 10 },
        { data: '2026-07-04', plotado: 13 },
      ] },
      { ticker: 'B', pontos: [
        { data: '2026-07-01', plotado: 20 },
        { data: '2026-07-02', plotado: 21 },
        { data: '2026-07-03', plotado: 22 },
        { data: '2026-07-04', plotado: 23 },
      ] },
    ]);

    expect(series[0].valores).toEqual([10, 10, 10, 13]);
  });

  it('antes da primeira cotação fica null, porque não há o que repetir', () => {
    const { series } = alinharEmEixoComum([
      { ticker: 'ANTIGO3', pontos: [
        { data: '2026-07-01', plotado: 1 },
        { data: '2026-07-02', plotado: 2 },
      ] },
      { ticker: 'NOVO3', pontos: [{ data: '2026-07-02', plotado: 50 }] },
    ]);

    expect(series[1].valores).toEqual([null, 50]);
  });

  it('ordena o eixo por data, independente da ordem de chegada', () => {
    const { datas } = alinharEmEixoComum([
      { ticker: 'A', pontos: [
        { data: '2026-07-10', plotado: 1 },
        { data: '2026-07-02', plotado: 2 },
      ] },
    ]);

    expect(datas).toEqual(['2026-07-02', '2026-07-10']);
  });

  it('lista vazia não quebra', () => {
    expect(alinharEmEixoComum([])).toEqual({ datas: [], series: [] });
  });
});
