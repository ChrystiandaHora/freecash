/**
 * Tradução de erros da API para mensagens exibíveis no formulário.
 *
 * O backend passou a responder erros de validação no formato por campo do DRF,
 * `{"campo": ["mensagem"]}`, em vez do antigo `{"detail": "mensagem"}`. Isso
 * permite apontar o problema no campo certo em vez de exibir um aviso genérico no
 * topo — mas exige que o cliente saiba ler os dois formatos, já que erros de
 * autenticação e de permissão continuam usando `detail`.
 *
 * @module lib/apiErros
 */

/**
 * Extrai erros por campo e uma mensagem geral a partir de uma falha do axios.
 *
 * @param {unknown} erro - Erro capturado da chamada à API.
 * @param {string} [fallback] - Mensagem usada quando nada mais é identificável.
 * @returns {{porCampo: Record<string, string>, geral: string}}
 */
export function extrairErros(erro, fallback = 'Não foi possível concluir a operação. Tente novamente.') {
  const resposta = erro?.response;
  const dados = resposta?.data;

  if (!resposta) {
    return { porCampo: {}, geral: 'Sem conexão com o servidor. Verifique sua internet.' };
  }

  if (resposta.status === 429) {
    return {
      porCampo: {},
      geral: 'Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente.',
    };
  }

  if (typeof dados === 'string') {
    return { porCampo: {}, geral: fallback };
  }

  if (!dados || typeof dados !== 'object') {
    return { porCampo: {}, geral: fallback };
  }

  const porCampo = {};
  let geral = '';

  for (const [chave, valor] of Object.entries(dados)) {
    const texto = Array.isArray(valor) ? valor.join(' ') : String(valor);
    if (chave === 'detail' || chave === 'non_field_errors') {
      geral = texto;
    } else if (chave === 'codigo') {
      // Código de correlação do erro 500: útil no suporte, não para o usuário.
      continue;
    } else {
      porCampo[chave] = texto;
    }
  }

  if (!geral && Object.keys(porCampo).length === 0) {
    geral = fallback;
  }

  return { porCampo, geral };
}
