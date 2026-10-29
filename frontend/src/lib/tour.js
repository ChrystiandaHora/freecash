/**
 * Regras puras do tour guiado: qual tour vale para a rota, onde o balão cabe, quais
 * passos têm o que mostrar e quais tours já abriram sozinhos neste navegador.
 *
 * O DOM fica de fora daqui (ver `components/tour/`): estas funções recebem retângulos
 * e um armazenamento injetável, para serem testadas sem navegador.
 */

const CHAVE_DOS_VISTOS = 'freecash_tours_vistos';

/**
 * Casa um caminho com as chaves de um mapa de rotas, aceitando parâmetros (`:id`).
 * A primeira chave que servir vence, então rotas fixas vêm antes das paramétricas.
 *
 * @param {Record<string, T>} mapa Rotas → valor.
 * @param {string} caminho `location.pathname`.
 * @returns {{padrao: string, valor: T}|null} A chave casada e o seu valor.
 * @template T
 */
export function casarRota(mapa, caminho) {
  for (const padrao of Object.keys(mapa)) {
    const escapado = padrao.replace(/([.+*?=^!:${}()[\]|/\\])/g, '\\$1');
    const regex = new RegExp(`^${escapado.replace(/\\:[a-zA-Z0-9_]+/g, '[^/]+')}$`);
    if (regex.test(caminho)) return { padrao, valor: mapa[padrao] };
  }
  return null;
}

const limitar = (valor, minimo, maximo) => Math.min(Math.max(valor, minimo), Math.max(minimo, maximo));

/**
 * Escolhe onde o balão fica em relação ao alvo: abaixo, acima, à direita, à esquerda
 * ou, sem espaço em volta, sobre a parte de baixo da tela.
 *
 * @param {object} p
 * @param {{top: number, left: number, width: number, height: number, bottom: number, right: number}|null} p.alvo
 *   Retângulo do alvo na viewport; null para um passo sem alvo (balão centralizado).
 * @param {{largura: number, altura: number}} p.balao Tamanho do balão.
 * @param {{largura: number, altura: number}} p.janela Tamanho da viewport.
 * @param {number} p.topoLivre Primeiro pixel abaixo do header fixo.
 * @param {number} p.margem Distância mínima das bordas.
 * @param {number} p.espaco Distância entre o alvo e o balão.
 * @returns {{lado: string, top: number, left: number}} Posição na viewport.
 */
export function posicionarBalao({ alvo, balao, janela, topoLivre, margem, espaco }) {
  const maxTop = janela.altura - margem - balao.altura;
  const maxLeft = janela.largura - margem - balao.largura;

  if (!alvo) {
    return {
      lado: 'centro',
      top: Math.round((janela.altura - balao.altura) / 2),
      left: Math.round((janela.largura - balao.largura) / 2),
    };
  }

  const leftCentralizado = limitar(alvo.left + alvo.width / 2 - balao.largura / 2, margem, maxLeft);
  const topCentralizado = limitar(alvo.top + alvo.height / 2 - balao.altura / 2, topoLivre, maxTop);

  const abaixo = alvo.bottom + espaco;
  if (abaixo <= maxTop) return { lado: 'abaixo', top: abaixo, left: leftCentralizado };

  const acima = alvo.top - espaco - balao.altura;
  if (acima >= topoLivre) return { lado: 'acima', top: acima, left: leftCentralizado };

  const direita = alvo.right + espaco;
  if (direita <= maxLeft) return { lado: 'direita', top: topCentralizado, left: direita };

  const esquerda = alvo.left - espaco - balao.largura;
  if (esquerda >= margem) return { lado: 'esquerda', top: topCentralizado, left: esquerda };

  return { lado: 'sobre', top: maxTop, left: leftCentralizado };
}

/**
 * Descarta os passos cujo alvo não está na tela agora (lista vazia, seção que só
 * aparece com dados, elemento escondido no mobile). Passo sem alvo sempre fica.
 *
 * @param {Array<{alvo?: string}>} passos Passos do tour da rota.
 * @param {(alvo: string) => boolean} existe Diz se o alvo está visível.
 * @returns {Array} Os passos mostráveis, na ordem original.
 */
export function passosDisponiveis(passos, existe) {
  return passos.filter((passo) => !passo.alvo || existe(passo.alvo));
}

function lerVistos(storage) {
  try {
    const lista = JSON.parse(storage.getItem(CHAVE_DOS_VISTOS) || '[]');
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}

/**
 * Diz se o tour desta rota já abriu sozinho neste navegador.
 *
 * @param {string} padrao Padrão da rota (`/eventos/:id`, não `/eventos/42`).
 * @param {Storage} [storage] Armazenamento (injetável para teste).
 * @returns {boolean} Verdadeiro se já foi visto. Armazenamento indisponível conta como não.
 */
export function tourJaVisto(padrao, storage = globalThis.localStorage) {
  return lerVistos(storage).includes(padrao);
}

/**
 * Registra que o tour da rota já abriu, para não abrir sozinho de novo.
 *
 * @param {string} padrao Padrão da rota.
 * @param {Storage} [storage] Armazenamento (injetável para teste).
 */
export function marcarTourVisto(padrao, storage = globalThis.localStorage) {
  try {
    const vistos = lerVistos(storage);
    if (!vistos.includes(padrao)) storage.setItem(CHAVE_DOS_VISTOS, JSON.stringify([...vistos, padrao]));
  } catch {
    // Navegação privada ou cota cheia: o tour volta a abrir na próxima visita, nada quebra
  }
}
