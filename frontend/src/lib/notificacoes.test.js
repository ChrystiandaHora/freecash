/**
 * Testes das notificações do sino.
 *
 * Duas distinções importam: conta sem e-mail e conta com e-mail não confirmado (pedir
 * para "confirmar" a quem não tem endereço seria um beco sem saída), e notificação lida
 * versus notificação com novidade — a lida sai do contador, mas volta se o assunto mudar.
 */
import { describe, expect, it } from 'vitest';
import { lerLidas, marcarLida, montarNotificacoes, naoLidas } from './notificacoes';

const CONFIRMADO = { email: 'ana@exemplo.com', email_verificado: true };
const NAO_CONFIRMADO = { email: 'ana@exemplo.com', email_verificado: false };
const DOIS_SINAIS = [
  { posicao_id: 7, tipo: 'REALIZAR' },
  { posicao_id: 3, tipo: 'APORTAR' },
];

/** Armazenamento em memória com a interface do `localStorage`. */
function storageFalso() {
  const dados = new Map();
  return {
    getItem: (chave) => dados.get(chave) ?? null,
    setItem: (chave, valor) => dados.set(chave, String(valor)),
  };
}

const storageQuebrado = {
  getItem: () => {
    throw new Error('indisponível');
  },
  setItem: () => {
    throw new Error('cota cheia');
  },
};

describe('montarNotificacoes', () => {
  it('não notifica sem perfil carregado e sem sinais', () => {
    expect(montarNotificacoes(null)).toEqual([]);
    expect(montarNotificacoes(undefined, [])).toEqual([]);
  });

  it('não notifica quando o e-mail está confirmado e não há sinais', () => {
    expect(montarNotificacoes(CONFIRMADO)).toEqual([]);
  });

  it('pede a confirmação quando há e-mail não confirmado', () => {
    const [notificacao, ...resto] = montarNotificacoes(NAO_CONFIRMADO);

    expect(resto).toEqual([]);
    expect(notificacao.id).toBe('email-nao-confirmado');
    expect(notificacao.destino).toBe('/conta');
  });

  it('pede o cadastro, e não a confirmação, quando a conta não tem e-mail', () => {
    const [notificacao] = montarNotificacoes({ email: '', email_verificado: false });

    expect(notificacao.id).toBe('email-ausente');
    expect(notificacao.titulo).not.toMatch(/confirme/i);
  });

  it('leva os sinais ao painel do Balanceamento, pela âncora', () => {
    const [notificacao] = montarNotificacoes(CONFIRMADO, DOIS_SINAIS);

    expect(notificacao.id).toBe('sinais-rebalanceamento');
    expect(notificacao.titulo).toBe('2 sinais de rebalanceamento');
    expect(notificacao.destino).toBe('/investimentos/balanceamento#sinais');
  });

  it('usa o singular para um único sinal', () => {
    const [notificacao] = montarNotificacoes(CONFIRMADO, [DOIS_SINAIS[0]]);

    expect(notificacao.titulo).toBe('1 sinal de rebalanceamento');
  });

  it('lista os sinais antes do e-mail quando há os dois', () => {
    const ids = montarNotificacoes(NAO_CONFIRMADO, DOIS_SINAIS).map((notificacao) => notificacao.id);

    expect(ids).toEqual(['sinais-rebalanceamento', 'email-nao-confirmado']);
  });

  it('dá a mesma assinatura aos mesmos sinais em qualquer ordem', () => {
    const [direta] = montarNotificacoes(CONFIRMADO, DOIS_SINAIS);
    const [invertida] = montarNotificacoes(CONFIRMADO, [...DOIS_SINAIS].reverse());

    expect(direta.assinatura).toBe(invertida.assinatura);
  });
});

describe('notificações lidas', () => {
  it('a notificação marcada como lida sai das não lidas, e as outras ficam', () => {
    const storage = storageFalso();
    const todas = montarNotificacoes(NAO_CONFIRMADO, DOIS_SINAIS);

    const lidas = marcarLida(todas[0], todas, [], storage);

    expect(naoLidas(todas, lidas).map((notificacao) => notificacao.id)).toEqual([
      'email-nao-confirmado',
    ]);
    expect(lerLidas(storage)).toEqual(lidas);
  });

  it('um sinal novo faz a notificação de sinais voltar', () => {
    const antes = montarNotificacoes(CONFIRMADO, DOIS_SINAIS);
    const lidas = marcarLida(antes[0], antes, [], storageFalso());

    const depois = montarNotificacoes(CONFIRMADO, [...DOIS_SINAIS, { posicao_id: 9, tipo: 'REALIZAR' }]);

    expect(naoLidas(depois, lidas)).toHaveLength(1);
  });

  it('trocar o e-mail faz o aviso voltar', () => {
    const antes = montarNotificacoes(NAO_CONFIRMADO);
    const lidas = marcarLida(antes[0], antes, [], storageFalso());

    const depois = montarNotificacoes({ email: 'ana@novo.com', email_verificado: false });

    expect(naoLidas(depois, lidas)).toHaveLength(1);
  });

  it('descarta as assinaturas que não existem mais, para a lista não crescer', () => {
    const storage = storageFalso();
    const antigas = ['sinais:1-APORTAR', 'email-nao-confirmado:velho@exemplo.com'];
    const todas = montarNotificacoes(NAO_CONFIRMADO, DOIS_SINAIS);

    const lidas = marcarLida(todas[1], todas, antigas, storage);

    expect(lidas).toEqual([todas[1].assinatura]);
  });

  it('não duplica a assinatura ao marcar a mesma notificação duas vezes', () => {
    const todas = montarNotificacoes(NAO_CONFIRMADO);
    const uma = marcarLida(todas[0], todas, [], storageFalso());

    expect(marcarLida(todas[0], todas, uma, storageFalso())).toEqual(uma);
  });

  it('armazenamento indisponível não quebra a leitura nem a marcação', () => {
    const todas = montarNotificacoes(NAO_CONFIRMADO);

    expect(lerLidas(storageQuebrado)).toEqual([]);
    expect(marcarLida(todas[0], todas, [], storageQuebrado)).toEqual([todas[0].assinatura]);
  });

  it('conteúdo corrompido no armazenamento conta como nenhuma lida', () => {
    const storage = storageFalso();
    storage.setItem('freecash_notificacoes_lidas', '{"não": "é lista"}');

    expect(lerLidas(storage)).toEqual([]);
  });
});
