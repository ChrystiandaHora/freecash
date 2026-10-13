/**
 * Leitura e filtro das despesas listadas no detalhe de um evento.
 *
 * Os lançamentos vêm de `GET /api/financeiro/eventos/:id/resumo/`, serializados por
 * `ContasPagarAPISerializer`: o nome da categoria chega em `categoria` (string ou
 * null), não em `categoria_nome`.
 */

/**
 * Nome da categoria para exibição na tabela.
 *
 * @param {{ categoria?: string | null }} lancamento
 * @returns {string} O nome, ou "—" quando a conta não tem categoria.
 */
export function nomeCategoria(lancamento) {
  return lancamento.categoria || '—';
}

/**
 * Filtra os lançamentos pela descrição ou pelo nome da categoria.
 *
 * @param {Array<{ descricao?: string, categoria?: string | null }>} lancamentos
 * @param {string} busca Texto digitado; vazio ou só espaços devolve a lista inteira.
 * @returns {Array} Os lançamentos que contêm o termo, sem diferenciar maiúsculas.
 */
export function filtrarLancamentos(lancamentos, busca) {
  const termo = busca.trim().toLowerCase();
  if (!termo) return lancamentos;
  return lancamentos.filter(
    (l) =>
      l.descricao?.toLowerCase().includes(termo) ||
      l.categoria?.toLowerCase().includes(termo)
  );
}
