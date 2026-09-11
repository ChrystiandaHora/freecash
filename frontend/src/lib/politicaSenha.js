/**
 * Espelho da política de senha do servidor, para a tela poder avisar enquanto o
 * usuário digita.
 *
 * A fonte da verdade continua sendo `backend/core/validacao_senha.py` — aqui não há
 * decisão nenhuma, só a mesma regra reescrita em JS. Foi para permitir este espelho
 * que a regra de contexto deixou de ser similaridade difusa (o `SequenceMatcher` a
 * 0,7 do Django, irreproduzível no cliente) e passou a ser contenção.
 *
 * Duas regras do servidor NÃO são espelhadas, de propósito: a lista das ~20 mil senhas
 * mais comuns, que não vale baixar para o navegador, e a unicidade do usuário. Por isso
 * `atendida` significa «passou no que dá para conferir aqui», nunca «o servidor vai
 * aceitar» — a resposta do POST continua sendo a palavra final, e a tela precisa
 * continuar tratando o erro de campo que vier de lá.
 *
 * Ver `docs/autenticacao.md` para a política e o porquê dela.
 */

export const TAMANHO_MINIMO = 12;
export const TAMANHO_MAXIMO = 128;
export const TAMANHO_MINIMO_TERMO = 4;
export const NOME_DO_SERVICO = 'freecash';

/**
 * Reduz um texto à forma usada na comparação: minúsculas e sem acento.
 *
 * @param {string} texto Texto de origem, possivelmente vazio ou nulo.
 * @returns {string} Texto em minúsculas, sem sinais diacríticos.
 */
export function normalizar(texto) {
  if (!texto) return '';
  return String(texto)
    .normalize('NFKD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}

/**
 * Monta os termos que a senha não pode conter, já normalizados.
 *
 * O e-mail entra pelo local-part; o domínio fica de fora porque barrar «gmail»
 * recusaria senha boa sem defender desta conta. Termos com menos de
 * `TAMANHO_MINIMO_TERMO` caracteres são descartados: um usuário «ana» barraria
 * «planalto».
 *
 * @param {{usuario?: string, email?: string, nome?: string}} [dados] Identificadores conhecidos pela tela.
 * @returns {string[]} Termos normalizados, sem repetição.
 */
export function termosDeContexto({ usuario = '', email = '', nome = '' } = {}) {
  const brutos = [NOME_DO_SERVICO, usuario, nome, String(email || '').split('@')[0]];

  const termos = [];
  for (const bruto of brutos) {
    const termo = normalizar(bruto);
    if (termo.length >= TAMANHO_MINIMO_TERMO && !termos.includes(termo)) {
      termos.push(termo);
    }
  }
  return termos;
}

/**
 * Avalia a senha contra os requisitos que o cliente consegue conferir.
 *
 * O estado `no-servidor` existe para a tela de redefinição por link: lá só chegam
 * `uid` e `token`, então a página não sabe o usuário nem o e-mail e não pode prometer
 * nada sobre o requisito de contexto. Mostrar o item como atendido seria mentira, e
 * escondê-lo devolveria a recusa-surpresa que motivou esta tela toda.
 *
 * @param {string} senha Senha digitada.
 * @param {object} [opcoes] Opções.
 * @param {string[]} [opcoes.termos] Termos de contexto, de `termosDeContexto`.
 * @param {boolean} [opcoes.contextoConhecido] `false` quando a tela não conhece os identificadores.
 * @param {string} [opcoes.confirmacao] Quando presente, acrescenta o requisito de coincidência.
 * @returns {{requisitos: Array<{id: string, rotulo: string, estado: 'atendido'|'pendente'|'no-servidor'}>, atendida: boolean, resumo: string}}
 */
export function avaliarSenha(senha, opcoes = {}) {
  const {
    termos = [],
    contextoConhecido = true,
    confirmacao,
  } = opcoes;

  const valor = senha || '';
  const alvo = normalizar(valor);
  const requisitos = [];

  const longaDemais = valor.length > TAMANHO_MAXIMO;
  requisitos.push({
    id: 'tamanho',
    rotulo: longaDemais
      ? `No máximo ${TAMANHO_MAXIMO} caracteres`
      : `Pelo menos ${TAMANHO_MINIMO} caracteres`,
    estado:
      !longaDemais && valor.length >= TAMANHO_MINIMO ? 'atendido' : 'pendente',
  });

  requisitos.push({
    id: 'nao-numerica',
    rotulo: 'Não pode ser só números',
    estado: valor && !/^\d+$/.test(valor) ? 'atendido' : 'pendente',
  });

  const contemTermo = termos.some((termo) => alvo.includes(termo));
  requisitos.push({
    id: 'contexto',
    rotulo: 'Sem seu nome de usuário, seu e-mail ou «freecash»',
    estado: !contextoConhecido
      ? 'no-servidor'
      : valor && !contemTermo
        ? 'atendido'
        : 'pendente',
  });

  if (confirmacao !== undefined) {
    requisitos.push({
      id: 'confirmacao',
      rotulo: 'As duas senhas coincidem',
      estado: valor && valor === confirmacao ? 'atendido' : 'pendente',
    });
  }

  const pendentes = requisitos.filter((r) => r.estado === 'pendente');

  return {
    requisitos,
    atendida: pendentes.length === 0,
    resumo: pendentes.length
      ? `Falta: ${pendentes.map((r) => r.rotulo.toLowerCase()).join('; ')}.`
      : 'Todos os requisitos de senha que conferimos aqui estão atendidos.',
  };
}

/**
 * Devolve o primeiro requisito ainda não atendido, para usar como erro de campo.
 *
 * Devolve o requisito inteiro, e não só o texto, porque quem chama precisa do `id`
 * para saber em qual campo marcar o erro — «as duas senhas coincidem» pertence ao
 * campo de confirmação, os demais ao campo de senha.
 *
 * @param {ReturnType<typeof avaliarSenha>} avaliacao Avaliação já calculada.
 * @returns {{id: string, rotulo: string, estado: string}|null} Requisito pendente, ou `null`.
 */
export function primeiroPendente(avaliacao) {
  return avaliacao.requisitos.find((r) => r.estado === 'pendente') || null;
}
