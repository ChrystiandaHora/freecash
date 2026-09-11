/**
 * Seleção de quais ativos o gráfico de Meus Ativos plota.
 *
 * O gráfico abre com os 2 maiores e os 2 menores retornos, e o usuário acrescenta ou
 * remove ativos a partir daí. Estas funções são a parte que decide *quem* entra e *com
 * qual cor* — a conversão dos valores mora em `cotacoesSerie.js`.
 *
 * Duas regras não óbvias justificam o arquivo existir separado do componente.
 *
 * **O teto de 8 é uma exigência da paleta, não uma preferência.** São 8 tons validados
 * para daltonismo e 4 tracejados. Como 8 e 4 não são coprimos, `slot % 8` e `slot % 4`
 * voltam a coincidir no slot 8: a nona linha sairia com cor *e* traço idênticos aos da
 * primeira, sem nenhum canal que as separasse. Limitar a seleção a `MAX_SERIES` torna a
 * colisão impossível por construção.
 *
 * **O slot é do ativo, não da posição dele na lista.** Remover uma linha não pode
 * repintar as outras — quem estava olhando a linha azul continuaria olhando o mesmo
 * lugar e leria outro papel. Por isso `adicionarAtivo` toma o menor slot livre e
 * `removerAtivo` devolve o slot ao bolo sem deslocar ninguém.
 */

/** Teto de séries simultâneas, igual ao tamanho da paleta categórica. */
export const MAX_SERIES = 8;

/** Quantos ativos a semente pega de cada ponta do ranking de retorno. */
export const EXTREMOS_POR_PONTA = 2;

/**
 * Diz se o retorno de um ativo é um número real ou o zero de guarda do backend.
 *
 * `Ativo.rentabilidade_percentual` devolve 0 quando `valor_investido` é zero, e
 * `recalcular_ativo` zera o preço médio quando a quantidade zera. Logo todo ativo
 * liquidado chega como "0%", indistinguível de um papel que de fato empatou. Sem este
 * corte, um ativo vendido ganharia a ponta de baixo do ranking de quem está no
 * prejuízo — e seria descartado na hora de desenhar, porque sem preço médio não há
 * retorno a plotar.
 *
 * @param {{preco_medio?: string|number, rentabilidade_percentual?: string|number}} [ativo]
 * @returns {boolean}
 */
function temRetornoReal(ativo) {
  if (!ativo) return false;
  return (
    parseFloat(ativo.preco_medio ?? 0) > 0 &&
    Number.isFinite(parseFloat(ativo.rentabilidade_percentual))
  );
}

/**
 * Ordena as séries por retorno, da maior para a menor.
 *
 * O desempate por ticker é explícito de propósito. A API já devolve os ativos em ordem
 * de ticker (`Ativo.Meta.ordering`) e `Array.sort` é estável, então na prática o empate
 * se resolveria sozinho — mas isso é contrato não declarado do backend, e a semente
 * virou um valor que o usuário vê. Sem o desempate, um universo todo empatado em 0%
 * escolheria ativos diferentes a cada refetch.
 *
 * @param {Array<{id: number, ticker: string}>} series
 * @param {Map<number, object>} ativosPorId
 * @returns {Array<{id: number, ticker: string}>} Só as séries com retorno real.
 */
export function rankearPorRetorno(series, ativosPorId = new Map()) {
  return series
    .filter((serie) => temRetornoReal(ativosPorId.get(serie.id)))
    .slice()
    .sort((a, b) => {
      const retornoA = parseFloat(ativosPorId.get(a.id).rentabilidade_percentual);
      const retornoB = parseFloat(ativosPorId.get(b.id).rentabilidade_percentual);
      if (retornoA !== retornoB) return retornoB - retornoA;
      return a.ticker.localeCompare(b.ticker, 'pt-BR');
    });
}

/**
 * Numera uma lista de ativos nos slots 0, 1, 2… na ordem em que aparecem.
 *
 * @param {Array<{id: number}>} ativos
 * @returns {Array<{id: number, slot: number}>}
 */
function comSlots(ativos) {
  return ativos.map((ativo, i) => ({ id: ativo.id, slot: i }));
}

/**
 * Escolhe a seleção inicial: os `EXTREMOS_POR_PONTA` maiores e menores retornos.
 *
 * A união é deduplicada preservando a ordem, com os maiores primeiro. Num universo de
 * três ativos o do meio é ao mesmo tempo o segundo maior e o segundo menor, e sem a
 * dedupe ele ocuparia dois slots — a legenda abriria com uma cor faltando no meio.
 *
 * Quando ninguém tem retorno real (a aba Arquivados, onde os ativos liquidados têm
 * preço médio zero), cai nos primeiros por ticker. Eles não desenham nada na escala
 * «Retorno», mas desenham em «Preço (R$)», que é a leitura que faz sentido ali; abrir
 * com o gráfico vazio e quatro chips seria pior que abrir com um aviso.
 *
 * @param {Array<{id: number, ticker: string}>} series Todas as séries do universo.
 * @param {Map<number, object>} ativosPorId Preço médio e retorno como a tabela os exibe.
 * @returns {Array<{id: number, slot: number}>}
 */
export function escolherExtremos(series, ativosPorId = new Map()) {
  const rankeadas = rankearPorRetorno(series, ativosPorId);

  if (rankeadas.length === 0) {
    const porTicker = series
      .slice()
      .sort((a, b) => a.ticker.localeCompare(b.ticker, 'pt-BR'))
      .slice(0, EXTREMOS_POR_PONTA * 2);
    return comSlots(porTicker);
  }

  const maiores = rankeadas.slice(0, EXTREMOS_POR_PONTA);
  const menores = rankeadas.slice(-EXTREMOS_POR_PONTA);

  const vistos = new Set();
  const unicos = [...maiores, ...menores].filter((serie) => {
    if (vistos.has(serie.id)) return false;
    vistos.add(serie.id);
    return true;
  });

  return comSlots(unicos.slice(0, MAX_SERIES));
}

/**
 * Devolve o menor slot de cor ainda livre.
 *
 * Menor livre, e não "o próximo da sequência": depois de remover a linha do slot 1, a
 * próxima adição deve reaproveitá-lo em vez de pular para o 4 e esgotar a paleta com
 * cinco linhas na tela.
 *
 * @param {Array<{slot: number}>} selecionados
 * @returns {number|null} Slot livre, ou null quando a seleção está cheia.
 */
export function primeiroSlotLivre(selecionados = []) {
  const ocupados = new Set(selecionados.map((s) => s.slot));
  for (let slot = 0; slot < MAX_SERIES; slot += 1) {
    if (!ocupados.has(slot)) return slot;
  }
  return null;
}

/**
 * Acrescenta um ativo à seleção.
 *
 * Devolve o motivo da recusa em vez de `null` ou exceção: as três mensagens que a tela
 * mostra ("já está no gráfico", "o gráfico comporta 8") derivam daqui, de uma fonte só
 * e testada, em vez de condicionais espalhadas pelo JSX.
 *
 * @param {Array<{id: number, slot: number}>} selecionados
 * @param {number} id
 * @returns {{selecionados: Array<{id: number, slot: number}>,
 *   resultado: 'adicionado'|'duplicado'|'cheio'}} Na recusa, `selecionados` volta pela
 *   mesma referência, para não disparar re-render à toa.
 */
export function adicionarAtivo(selecionados = [], id) {
  if (selecionados.some((s) => s.id === id)) {
    return { selecionados, resultado: 'duplicado' };
  }

  const slot = primeiroSlotLivre(selecionados);
  if (slot === null) {
    return { selecionados, resultado: 'cheio' };
  }

  return { selecionados: [...selecionados, { id, slot }], resultado: 'adicionado' };
}

/**
 * Remove um ativo da seleção, liberando o slot sem mexer nos demais.
 *
 * @param {Array<{id: number, slot: number}>} selecionados
 * @param {number} id
 * @returns {Array<{id: number, slot: number}>}
 */
export function removerAtivo(selecionados = [], id) {
  return selecionados.filter((s) => s.id !== id);
}

/**
 * Descarta da seleção os ativos que saíram do universo.
 *
 * Excluir um ativo, transferir a custódia inteira ou arquivá-lo encolhe a lista sem
 * mudar a carteira nem a aba, então a remontagem que reseta a seleção não acontece e o
 * estado fica guardando um id que não existe mais. Aplicar isto no render é idempotente;
 * podar o estado por efeito colateral entraria em laço.
 *
 * @param {Array<{id: number, slot: number}>} selecionados
 * @param {Set<number>} idsValidos
 * @returns {Array<{id: number, slot: number}>}
 */
export function sanearSelecao(selecionados = [], idsValidos = new Set()) {
  return selecionados.filter((s) => idsValidos.has(s.id));
}

/**
 * Resolve o que o usuário digitou num ativo do universo.
 *
 * O `<datalist>` sugere, mas não restringe: o campo aceita texto livre, e o usuário
 * tanto digita "petr" quanto cola o rótulo inteiro da sugestão. A ordem das tentativas
 * vai do mais específico ao mais frouxo, e ambiguidade é recusa — com PETR3 e PETR4 na
 * carteira, "PETR" não pode escolher um dos dois no chute.
 *
 * @param {string} texto
 * @param {Array<{id: number, ticker: string, nome?: string}>} series
 * @param {Set<number>} [idsSelecionados]
 * @returns {{id: number}|{erro: 'vazio'|'nao-encontrado'|'ja-selecionado'}}
 */
export function resolverBusca(texto, series = [], idsSelecionados = new Set()) {
  // O rótulo da sugestão é "TICKER — Nome"; colado inteiro, só o ticker interessa
  const bruto = String(texto ?? '').split('—')[0].trim();
  if (!bruto) return { erro: 'vazio' };

  const alvo = normalizar(bruto);
  const candidatos = [
    series.filter((s) => normalizar(s.ticker) === alvo),
    series.filter((s) => normalizar(s.ticker).startsWith(alvo)),
    series.filter(
      (s) => normalizar(s.ticker).includes(alvo) || normalizar(s.nome).includes(alvo)
    ),
  ];

  const achado = candidatos.find((lista) => lista.length === 1)?.[0];
  if (!achado) return { erro: 'nao-encontrado' };
  if (idsSelecionados.has(achado.id)) return { erro: 'ja-selecionado' };

  return { id: achado.id };
}

/**
 * Normaliza para comparação: sem acento, sem caixa, sem espaço nas pontas.
 *
 * @param {string} [valor]
 * @returns {string}
 */
function normalizar(valor) {
  return String(valor ?? '')
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

/**
 * Recorta as séries para os ativos selecionados, na ordem dos slots.
 *
 * A ordem dos slots é a mesma dos chips, da legenda e das colunas da tabela de dados.
 * Sem isto, um ativo acrescentado depois apareceria no meio da legenda, na posição em
 * que a API o devolveu.
 *
 * @param {Array<{id: number}>} series
 * @param {Array<{id: number, slot: number}>} selecionados
 * @returns {Array<{id: number}>}
 */
export function ordenarPorSlot(series = [], selecionados = []) {
  const porId = new Map(series.map((serie) => [serie.id, serie]));
  return selecionados
    .slice()
    .sort((a, b) => a.slot - b.slot)
    .map((s) => porId.get(s.id))
    .filter(Boolean);
}
