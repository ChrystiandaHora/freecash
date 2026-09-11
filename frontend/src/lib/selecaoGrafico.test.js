/**
 * Testes da seleção de ativos do gráfico de Meus Ativos.
 *
 * Três invariantes pagam o arquivo:
 *
 * 1. **Cor e traço distintos.** A paleta tem 8 tons e 4 tracejados; como não são
 *    coprimos, a nona linha repetiria os dois canais da primeira. O teste final encadeia
 *    a seleção com a conversão de `cotacoesSerie` e exige pares distintos.
 * 2. **O slot é do ativo.** Remover uma linha não pode repintar as outras, senão quem
 *    olhava a linha azul passa a ler outro papel no mesmo lugar.
 * 3. **Ativo liquidado fora do ranking.** O backend devolve 0% como guarda quando não
 *    há valor investido, indistinguível de um empate real — sem o corte, um ativo
 *    vendido ganha a ponta de baixo e some na hora de desenhar.
 *
 * `lib/selecaoGrafico.js` é puro — sem jsdom nem @testing-library.
 */
import { describe, expect, it } from 'vitest';
import {
  MAX_SERIES,
  adicionarAtivo,
  escolherExtremos,
  ordenarPorSlot,
  primeiroSlotLivre,
  rankearPorRetorno,
  removerAtivo,
  sanearSelecao,
  resolverBusca,
} from './selecaoGrafico';
import { alinharEmEixoComum, converterSeries } from './cotacoesSerie';

const serie = (id, ticker, nome = ticker) => ({ id, ticker, nome });

/** Listagem no formato que o DRF entrega: decimais como string. */
const listagem = (entradas) =>
  new Map(
    entradas.map(([id, precoMedio, retorno]) => [
      id,
      {
        preco_medio: String(precoMedio),
        rentabilidade_percentual: retorno === undefined ? undefined : String(retorno),
      },
    ])
  );

/** Universo de 6 ativos com retornos distintos, do melhor (F) ao pior (A). */
const SEIS = [
  serie(1, 'AAAA3'), serie(2, 'BBBB3'), serie(3, 'CCCC3'),
  serie(4, 'DDDD3'), serie(5, 'EEEE3'), serie(6, 'FFFF3'),
];
const SEIS_LISTAGEM = listagem([
  [1, 10, -30], [2, 10, -20], [3, 10, -5],
  [4, 10, 5], [5, 10, 20], [6, 10, 30],
]);

describe('rankearPorRetorno', () => {
  it('ordena do maior retorno para o menor', () => {
    const ordem = rankearPorRetorno(SEIS, SEIS_LISTAGEM).map((s) => s.ticker);
    expect(ordem).toEqual(['FFFF3', 'EEEE3', 'DDDD3', 'CCCC3', 'BBBB3', 'AAAA3']);
  });

  it('desempata por ticker, e não pela ordem de chegada', () => {
    const empatados = [serie(1, 'ZZZZ3'), serie(2, 'AAAA3'), serie(3, 'MMMM3')];
    const tudoZero = listagem([[1, 10, 0], [2, 10, 0], [3, 10, 0]]);

    const direto = rankearPorRetorno(empatados, tudoZero).map((s) => s.ticker);
    const embaralhado = rankearPorRetorno([...empatados].reverse(), tudoZero).map((s) => s.ticker);

    expect(direto).toEqual(['AAAA3', 'MMMM3', 'ZZZZ3']);
    expect(embaralhado).toEqual(direto);
  });

  it('exclui o ativo liquidado, cujo 0% é guarda do backend e não empate', () => {
    const universo = [serie(1, 'VIVO3'), serie(2, 'MORTO3')];
    const comLiquidado = listagem([[1, 10, -50], [2, 0, 0]]);

    expect(rankearPorRetorno(universo, comLiquidado).map((s) => s.ticker)).toEqual(['VIVO3']);
  });

  it('exclui retorno ausente sem tratá-lo como zero', () => {
    const universo = [serie(1, 'VIVO3'), serie(2, 'SEMDADO3')];
    expect(
      rankearPorRetorno(universo, listagem([[1, 10, -50], [2, 10, undefined]])).map((s) => s.ticker)
    ).toEqual(['VIVO3']);
  });

  it('exclui quem não está na listagem', () => {
    expect(rankearPorRetorno([serie(9, 'ORFAO3')], new Map())).toEqual([]);
  });
});

describe('escolherExtremos', () => {
  it('pega os 2 maiores e os 2 menores, maiores primeiro, em slots sequenciais', () => {
    const escolhidos = escolherExtremos(SEIS, SEIS_LISTAGEM);
    const porTicker = escolhidos.map((e) => SEIS.find((s) => s.id === e.id).ticker);

    expect(porTicker).toEqual(['FFFF3', 'EEEE3', 'BBBB3', 'AAAA3']);
    expect(escolhidos.map((e) => e.slot)).toEqual([0, 1, 2, 3]);
  });

  it('com 3 ativos o do meio entra nas duas pontas, sem ocupar dois slots', () => {
    const tres = SEIS.slice(0, 3);
    const escolhidos = escolherExtremos(tres, SEIS_LISTAGEM);

    expect(escolhidos).toHaveLength(3);
    // Sem a dedupe antes da numeração, a legenda abriria com um buraco no meio
    expect(escolhidos.map((e) => e.slot)).toEqual([0, 1, 2]);
    expect(new Set(escolhidos.map((e) => e.id)).size).toBe(3);
  });

  it('com 1 ativo devolve ele só; com nenhum, devolve vazio', () => {
    expect(escolherExtremos([SEIS[0]], SEIS_LISTAGEM)).toHaveLength(1);
    expect(escolherExtremos([], SEIS_LISTAGEM)).toEqual([]);
  });

  it('com 4 ativos devolve o universo inteiro', () => {
    expect(escolherExtremos(SEIS.slice(0, 4), SEIS_LISTAGEM)).toHaveLength(4);
  });

  it('sem ninguém rankeável cai nos primeiros por ticker (aba Arquivados)', () => {
    // Todo liquidado tem preço médio zero; o ranking não se aplica, mas «Preço (R$)» sim
    const arquivados = [serie(1, 'ZZZZ3'), serie(2, 'AAAA3'), serie(3, 'MMMM3')];
    const semPrecoMedio = listagem([[1, 0, 0], [2, 0, 0], [3, 0, 0]]);

    const escolhidos = escolherExtremos(arquivados, semPrecoMedio);
    const tickers = escolhidos.map((e) => arquivados.find((s) => s.id === e.id).ticker);

    expect(tickers).toEqual(['AAAA3', 'MMMM3', 'ZZZZ3']);
    expect(escolhidos.map((e) => e.slot)).toEqual([0, 1, 2]);
  });

  it('nunca passa do teto da paleta', () => {
    const muitos = Array.from({ length: 30 }, (_, i) => serie(i, `TICK${i}`));
    const todos = listagem(muitos.map((s) => [s.id, 10, s.id]));

    expect(escolherExtremos(muitos, todos).length).toBeLessThanOrEqual(MAX_SERIES);
  });
});

describe('primeiroSlotLivre / adicionarAtivo / removerAtivo', () => {
  it('a readição reaproveita o menor slot livre, em vez de avançar a sequência', () => {
    const cheio = [{ id: 1, slot: 0 }, { id: 2, slot: 1 }, { id: 3, slot: 2 }];
    const semOMeio = removerAtivo(cheio, 2);

    expect(primeiroSlotLivre(semOMeio)).toBe(1);
    expect(adicionarAtivo(semOMeio, 9).selecionados).toContainEqual({ id: 9, slot: 1 });
  });

  it('remover não desloca os demais — o slot segue a entidade', () => {
    const tres = [{ id: 1, slot: 0 }, { id: 2, slot: 1 }, { id: 3, slot: 2 }];
    expect(removerAtivo(tres, 2)).toEqual([{ id: 1, slot: 0 }, { id: 3, slot: 2 }]);
  });

  it('duplicado é recusado e devolve a MESMA referência', () => {
    const atual = [{ id: 1, slot: 0 }];
    const { selecionados, resultado } = adicionarAtivo(atual, 1);

    expect(resultado).toBe('duplicado');
    expect(selecionados).toBe(atual);
  });

  it('no teto recusa por cheio, sem mutar', () => {
    const cheio = Array.from({ length: MAX_SERIES }, (_, i) => ({ id: i, slot: i }));
    const { selecionados, resultado } = adicionarAtivo(cheio, 99);

    expect(resultado).toBe('cheio');
    expect(selecionados).toBe(cheio);
    expect(primeiroSlotLivre(cheio)).toBeNull();
  });

  it('remover id inexistente é no-op', () => {
    const atual = [{ id: 1, slot: 0 }];
    expect(removerAtivo(atual, 42)).toEqual(atual);
  });

  it('ciclo de encher, esvaziar e encher de novo mantém slots únicos em 0..7', () => {
    let selecao = [];
    for (let id = 0; id < MAX_SERIES; id += 1) selecao = adicionarAtivo(selecao, id).selecionados;
    for (let id = 0; id < MAX_SERIES; id += 1) selecao = removerAtivo(selecao, id);
    for (let id = 100; id < 100 + MAX_SERIES; id += 1) {
      selecao = adicionarAtivo(selecao, id).selecionados;
    }

    const slots = selecao.map((s) => s.slot).sort((a, b) => a - b);
    expect(slots).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });
});

describe('sanearSelecao', () => {
  it('descarta quem saiu do universo preservando ordem e slots de quem ficou', () => {
    const selecao = [{ id: 1, slot: 0 }, { id: 2, slot: 1 }, { id: 3, slot: 2 }];
    expect(sanearSelecao(selecao, new Set([1, 3]))).toEqual([
      { id: 1, slot: 0 },
      { id: 3, slot: 2 },
    ]);
  });

  it('universo vazio zera a seleção', () => {
    expect(sanearSelecao([{ id: 1, slot: 0 }], new Set())).toEqual([]);
  });
});

describe('resolverBusca', () => {
  const UNIVERSO = [
    serie(1, 'PETR3', 'Petrobras ON'),
    serie(2, 'PETR4', 'Petrobras PN'),
    serie(3, 'ITUB4', 'Itaú Unibanco'),
  ];

  it('acha por ticker exato, ignorando caixa e espaços', () => {
    expect(resolverBusca('  petr4 ', UNIVERSO)).toEqual({ id: 2 });
  });

  it('acha por prefixo único', () => {
    expect(resolverBusca('itu', UNIVERSO)).toEqual({ id: 3 });
  });

  it('prefixo ambíguo é recusa, não chute', () => {
    // PETR3 e PETR4 casam igualmente — escolher um seria adivinhar
    expect(resolverBusca('PETR', UNIVERSO)).toEqual({ erro: 'nao-encontrado' });
  });

  it('acha pelo nome sem acento', () => {
    expect(resolverBusca('itau', UNIVERSO)).toEqual({ id: 3 });
  });

  it('aceita o rótulo inteiro colado da sugestão', () => {
    expect(resolverBusca('PETR4 — Petrobras PN', UNIVERSO)).toEqual({ id: 2 });
  });

  it('distingue já selecionado de não encontrado', () => {
    expect(resolverBusca('PETR4', UNIVERSO, new Set([2]))).toEqual({ erro: 'ja-selecionado' });
    expect(resolverBusca('XPTO11', UNIVERSO)).toEqual({ erro: 'nao-encontrado' });
  });

  it('texto vazio tem erro próprio', () => {
    expect(resolverBusca('   ', UNIVERSO)).toEqual({ erro: 'vazio' });
  });
});

describe('ordenarPorSlot', () => {
  it('devolve na ordem dos slots e ignora quem não está selecionado', () => {
    const selecao = [{ id: 3, slot: 1 }, { id: 1, slot: 0 }];
    const ordenadas = ordenarPorSlot(SEIS, selecao).map((s) => s.ticker);

    expect(ordenadas).toEqual(['AAAA3', 'CCCC3']);
  });

  it('ignora selecionado que não tem série', () => {
    expect(ordenarPorSlot(SEIS, [{ id: 999, slot: 0 }])).toEqual([]);
  });
});

describe('seleção + conversão: cada linha tem um par (cor, traço) distinto', () => {
  // Trava a regressão real: com `cores[slot % 8]` e `TRACEJADOS[slot % 4]` sobre a
  // ordem alfabética de TODOS os ativos, o slot 8 saía idêntico ao slot 0 — mesma cor
  // e mesmo traço. O teto da seleção é o que torna isso impossível.
  const CORES = ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7'];
  const TRACEJADOS = [0, 3, 7, 12];

  it('quatro extremos de dez ativos rendem quatro pares distintos e séries alinhadas', () => {
    const dez = Array.from({ length: 10 }, (_, i) => ({
      ...serie(i + 1, `TICK${i}`),
      pontos: [
        { data: '2026-07-01', valor: 10 },
        { data: `2026-07-0${(i % 3) + 2}`, valor: 10 + i },
      ],
    }));
    const dezListagem = listagem(dez.map((s, i) => [s.id, 10, i * 3 - 10]));

    const selecionados = escolherExtremos(dez, dezListagem);
    const emOrdem = ordenarPorSlot(dez, selecionados);
    const convertidas = converterSeries(emOrdem, 'retorno', dezListagem);
    const { datas, series: alinhadas } = alinharEmEixoComum(convertidas);

    expect(alinhadas).toHaveLength(4);
    alinhadas.forEach((s) => expect(s.valores).toHaveLength(datas.length));

    const pares = selecionados.map(
      ({ slot }) => `${CORES[slot % CORES.length]}|${TRACEJADOS[slot % TRACEJADOS.length]}`
    );
    expect(new Set(pares).size).toBe(pares.length);
  });

  it('os oito slots da paleta rendem oito pares distintos', () => {
    const pares = Array.from({ length: MAX_SERIES }, (_, slot) =>
      `${CORES[slot % CORES.length]}|${TRACEJADOS[slot % TRACEJADOS.length]}`
    );
    expect(new Set(pares).size).toBe(MAX_SERIES);
  });
});
