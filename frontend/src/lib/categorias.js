/**
 * Regras puras do campo de categoria nos formulários de lançamento.
 *
 * O campo é um select com as categorias do usuário e uma última opção para criar
 * outra; o nome digitado ali vira categoria nova ao salvar
 * (`resolver_categoria_por_nome` no backend). Ver docs/contas.md.
 */

const ordenarPtBr = new Intl.Collator('pt-BR', { sensitivity: 'base' }).compare;

/**
 * Nomes das categorias de um tipo, em ordem alfabética.
 *
 * @param {Array<{ nome: string, tipo: string }> | undefined} categorias - Todas as
 *   categorias do usuário, como `/api/categorias/` devolve.
 * @param {'R' | 'D' | 'I'} tipo - Receita, despesa ou investimento.
 * @returns {string[]} Os nomes do tipo pedido; vazio enquanto a lista não chegou.
 */
export function nomesCategoriasPorTipo(categorias, tipo) {
  return (categorias ?? [])
    .filter((categoria) => categoria.tipo === tipo)
    .map((categoria) => categoria.nome)
    .sort(ordenarPtBr);
}

/**
 * Opções do select de categoria: as do tipo, mais o valor atual se ele não estiver lá.
 *
 * Sem o valor atual, um select cuja opção não existe aparece vazio — na edição de um
 * lançamento com categoria de outro tipo, ou antes de a lista chegar do servidor.
 *
 * @param {Array<{ nome: string, tipo: string }> | undefined} categorias
 * @param {'R' | 'D' | 'I'} tipo
 * @param {string} valorAtual - Nome da categoria selecionada no momento.
 * @returns {string[]} Nomes em ordem alfabética, sem repetição.
 */
export function opcoesCategoria(categorias, tipo, valorAtual) {
  const nomes = nomesCategoriasPorTipo(categorias, tipo);
  if (!valorAtual || nomes.includes(valorAtual)) {
    return nomes;
  }
  return [...nomes, valorAtual].sort(ordenarPtBr);
}
