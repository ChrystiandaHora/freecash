/**
 * Download de arquivos gerados pela API e leitura de erro em respostas `blob`.
 *
 * Ficam fora de `lib/` porque dependem do DOM (`document`, `URL.createObjectURL`).
 */

/**
 * Dispara o download de um conteúdo binário recebido da API.
 *
 * @param {BlobPart} dados Corpo da resposta.
 * @param {string} nome Nome do arquivo salvo.
 * @param {string} tipoMime Tipo MIME do arquivo.
 */
export function baixarArquivo(dados, nome, tipoMime) {
  const url = URL.createObjectURL(new Blob([dados], { type: tipoMime }));
  const link = document.createElement('a');
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Extrai a mensagem de erro da API. Com `responseType: 'blob'`, até o JSON de erro
 * chega como Blob e precisa ser lido antes.
 *
 * @param {unknown} erro Erro lançado pelo axios.
 * @param {string} padrao Mensagem usada quando a API não manda uma.
 * @returns {Promise<string>} Mensagem para exibir.
 */
export async function mensagemDeErro(erro, padrao) {
  const dados = erro?.response?.data;
  if (dados instanceof Blob) {
    try {
      // `detail` é o que o DRF manda no 429 do throttle
      const corpo = JSON.parse(await dados.text());
      return corpo.erro || corpo.detail || padrao;
    } catch {
      return padrao;
    }
  }
  return dados?.erro || dados?.detail || padrao;
}
