import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  STATUS_CONEXAO,
  aguardarConexao,
  assinarStatusConexao,
  classificarFalha,
  definirStatusConexao,
  ehFalhaDeConexao,
  intervaloDeTentativa,
  lerStatusConexao,
} from './statusConexao';

/** Monta um erro no formato do axios, só com o que o módulo lê. */
const erroAxios = ({ status, code } = {}) => ({
  isAxiosError: true,
  code,
  response: status ? { status } : undefined,
});

afterEach(() => {
  definirStatusConexao(STATUS_CONEXAO.ONLINE);
});

describe('ehFalhaDeConexao', () => {
  it('trata erro sem resposta como queda de conexão', () => {
    expect(ehFalhaDeConexao(erroAxios({ code: 'ERR_NETWORK' }))).toBe(true);
    expect(ehFalhaDeConexao(erroAxios({ code: 'ECONNABORTED' }))).toBe(true);
  });

  it.each([502, 503, 504])('trata %i do gateway como API indisponível', (status) => {
    expect(ehFalhaDeConexao(erroAxios({ status }))).toBe(true);
  });

  it.each([400, 401, 403, 404, 429, 500])('ignora %i, que é o Django respondendo', (status) => {
    expect(ehFalhaDeConexao(erroAxios({ status }))).toBe(false);
  });

  it('ignora requisição cancelada pelo React Query', () => {
    expect(ehFalhaDeConexao(erroAxios({ code: 'ERR_CANCELED' }))).toBe(false);
  });

  it('ignora o que não é erro do axios', () => {
    expect(ehFalhaDeConexao(new TypeError('x is undefined'))).toBe(false);
    expect(ehFalhaDeConexao(null)).toBe(false);
  });
});

describe('classificarFalha', () => {
  it('culpa a internet quando o navegador está offline', () => {
    expect(classificarFalha(false)).toBe(STATUS_CONEXAO.SEM_INTERNET);
  });

  it('culpa o servidor quando o navegador está online', () => {
    expect(classificarFalha(true)).toBe(STATUS_CONEXAO.API_INDISPONIVEL);
  });
});

describe('intervaloDeTentativa', () => {
  it('cresce a cada falha e estabiliza no teto', () => {
    expect([0, 1, 2, 3, 4, 50].map(intervaloDeTentativa)).toEqual([5, 10, 20, 30, 30, 30]);
  });

  it('não quebra com tentativa negativa', () => {
    expect(intervaloDeTentativa(-1)).toBe(5);
  });
});

describe('armazenamento do status', () => {
  it('avisa os assinantes só quando o status muda', () => {
    const ouvinte = vi.fn();
    const cancelar = assinarStatusConexao(ouvinte);

    definirStatusConexao(STATUS_CONEXAO.API_INDISPONIVEL);
    definirStatusConexao(STATUS_CONEXAO.API_INDISPONIVEL);
    cancelar();
    definirStatusConexao(STATUS_CONEXAO.ONLINE);

    expect(ouvinte).toHaveBeenCalledTimes(1);
    expect(lerStatusConexao()).toBe(STATUS_CONEXAO.ONLINE);
  });

  it('aguardarConexao resolve na hora quando já está online', async () => {
    await expect(aguardarConexao()).resolves.toBeUndefined();
  });

  it('aguardarConexao só resolve quando a conexão volta', async () => {
    definirStatusConexao(STATUS_CONEXAO.SEM_INTERNET);
    let resolvida = false;
    const espera = aguardarConexao().then(() => {
      resolvida = true;
    });

    definirStatusConexao(STATUS_CONEXAO.API_INDISPONIVEL);
    await Promise.resolve();
    expect(resolvida).toBe(false);

    definirStatusConexao(STATUS_CONEXAO.ONLINE);
    await espera;
    expect(resolvida).toBe(true);
  });
});
