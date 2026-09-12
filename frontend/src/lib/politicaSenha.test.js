import { describe, expect, it } from 'vitest';

import {
  TAMANHO_MAXIMO,
  TAMANHO_MINIMO,
  avaliarSenha,
  normalizar,
  primeiroPendente,
  termosDeContexto,
} from './politicaSenha';

const CONTEXTO = { usuario: 'chrystian', email: 'chrystian@inscode.com.br' };

/**
 * Mesma tabela de `CASOS_DE_PARIDADE` em
 * `backend/core/tests/test_politica_senha.py`. Um caso que mude de lado só aqui faz a
 * tela prometer o que o servidor recusa — o defeito que esta política veio corrigir.
 *
 * Os casos de senha comum ficam de fora: a lista das 20 mil não é espelhada no cliente.
 */
const CASOS_DE_PARIDADE = [
  ['roda gigante de terca', true, 'frase longa passa sem símbolo nenhum'],
  ['abacaxi-roxo', true, 'o mínimo de 12 é inclusivo'],
  ['abacaxi-rox', false, '11 caracteres reprova'],
  ['Chrystian18!', false, 'contém o nome de usuário, ainda que capitalizado'],
  ['Chrýstian18!', false, 'acento não escapa da comparação'],
  ['chrystian-e-o-sol', false, 'contém o local-part do e-mail'],
  ['freecash-rende-bem', false, 'contém o nome do serviço'],
  ['123456789012345', false, 'só dígitos reprova'],
];

describe('normalizar', () => {
  it('derruba maiúscula e acento, que não podem servir de escape', () => {
    expect(normalizar('Chrýstian')).toBe('chrystian');
    expect(normalizar('JOÃO')).toBe('joao');
  });

  it('aceita vazio e nulo sem estourar', () => {
    expect(normalizar('')).toBe('');
    expect(normalizar(null)).toBe('');
    expect(normalizar(undefined)).toBe('');
  });
});

describe('termosDeContexto', () => {
  it('junta serviço, usuário e local-part do e-mail', () => {
    expect(termosDeContexto({ usuario: 'chrystian', email: 'contato@inscode.com.br' }))
      .toEqual(['freecash', 'chrystian', 'contato']);
  });

  it('deixa o domínio do e-mail de fora', () => {
    expect(termosDeContexto({ usuario: 'joana', email: 'joana@gmail.com' }))
      .not.toContain('gmail');
  });

  it('descarta termo curto, que geraria falso positivo', () => {
    expect(termosDeContexto({ usuario: 'ana', email: 'ana@exemplo.com' }))
      .toEqual(['freecash']);
  });

  it('sem identificadores, sobra o nome do serviço', () => {
    expect(termosDeContexto()).toEqual(['freecash']);
  });
});

describe('avaliarSenha — paridade com o servidor', () => {
  const termos = termosDeContexto(CONTEXTO);

  it.each(CASOS_DE_PARIDADE)('%s → %s (%s)', (senha, aceita) => {
    expect(avaliarSenha(senha, { termos }).atendida).toBe(aceita);
  });

  it('recusa acima do teto e troca o rótulo do requisito de tamanho', () => {
    const avaliacao = avaliarSenha('a'.repeat(TAMANHO_MAXIMO + 1), { termos });
    expect(avaliacao.atendida).toBe(false);
    expect(avaliacao.requisitos[0].rotulo).toContain(String(TAMANHO_MAXIMO));
  });

  it('não exige maiúscula, dígito nem símbolo', () => {
    expect(avaliarSenha('cavalo bateria grampo', { termos }).atendida).toBe(true);
  });
});

describe('avaliarSenha — estados dos requisitos', () => {
  const termos = termosDeContexto(CONTEXTO);

  it('senha vazia deixa tudo pendente, sem marcar nada como atendido', () => {
    const { requisitos, atendida } = avaliarSenha('', { termos });
    expect(atendida).toBe(false);
    expect(requisitos.every((r) => r.estado === 'pendente')).toBe(true);
  });

  it('sem conhecer os identificadores, o contexto fica para o servidor', () => {
    const { requisitos, atendida } = avaliarSenha('roda gigante de terca', {
      contextoConhecido: false,
    });
    const contexto = requisitos.find((r) => r.id === 'contexto');

    expect(contexto.estado).toBe('no-servidor');
    // `no-servidor` não conta como pendente: não dá para exigir o que não dá para conferir
    expect(atendida).toBe(true);
  });

  it('o requisito de coincidência só aparece quando há campo de confirmação', () => {
    const semCampo = avaliarSenha('roda gigante de terca', { termos });
    expect(semCampo.requisitos.some((r) => r.id === 'confirmacao')).toBe(false);

    const divergente = avaliarSenha('roda gigante de terca', {
      termos,
      confirmacao: 'outra coisa',
    });
    expect(divergente.atendida).toBe(false);

    const igual = avaliarSenha('roda gigante de terca', {
      termos,
      confirmacao: 'roda gigante de terca',
    });
    expect(igual.atendida).toBe(true);
  });
});

describe('resumo e primeiroPendente', () => {
  const termos = termosDeContexto(CONTEXTO);

  it('o resumo lista o que falta, para ir ao vivo sem ler a lista inteira', () => {
    const { resumo } = avaliarSenha('curta', { termos });
    expect(resumo).toContain(`pelo menos ${TAMANHO_MINIMO} caracteres`);
  });

  it('o resumo confirma quando não falta nada aqui', () => {
    const { resumo } = avaliarSenha('roda gigante de terca', { termos });
    expect(resumo).toContain('atendidos');
  });

  it('primeiroPendente devolve o requisito que vira erro de campo', () => {
    const pendente = primeiroPendente(avaliarSenha('Chrystian18!', { termos }));
    expect(pendente.id).toBe('contexto');
    expect(pendente.rotulo).toContain('nome de usuário');

    expect(primeiroPendente(avaliarSenha('roda gigante de terca', { termos })))
      .toBeNull();
  });

  it('aponta o campo de confirmação quando é ele que está pendente', () => {
    const avaliacao = avaliarSenha('roda gigante de terca', {
      termos,
      confirmacao: 'outra coisa',
    });
    expect(primeiroPendente(avaliacao).id).toBe('confirmacao');
  });
});
