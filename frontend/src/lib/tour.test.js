/**
 * Testes das regras do tour guiado: casar a rota, posicionar o balão, filtrar passos
 * cujo alvo não está na tela e lembrar quais tours já abriram sozinhos.
 *
 * O posicionamento é o ponto mais frágil: o header fixo cobre os primeiros 64px da
 * viewport, então um balão "acima do alvo" calculado sem considerá-lo ficaria escondido
 * atrás da barra — legível no código, invisível na tela.
 */
import { describe, expect, it } from 'vitest';

import {
  casarRota,
  marcarTourVisto,
  passosDisponiveis,
  posicionarBalao,
  tourJaVisto,
} from './tour';

describe('casarRota', () => {
  const mapa = { '/backup': 'b', '/eventos/:id': 'e', '/investimentos/ativos/novo': 'n', '/investimentos/ativos/:id': 'd' };

  it('casa rota exata e rota com parâmetro', () => {
    expect(casarRota(mapa, '/backup')).toEqual({ padrao: '/backup', valor: 'b' });
    expect(casarRota(mapa, '/eventos/42')).toEqual({ padrao: '/eventos/:id', valor: 'e' });
  });

  it('não casa prefixo nem rota desconhecida', () => {
    expect(casarRota(mapa, '/backup/extra')).toBeNull();
    expect(casarRota(mapa, '/nada')).toBeNull();
  });

  it('respeita a ordem do mapa quando dois padrões servem', () => {
    expect(casarRota(mapa, '/investimentos/ativos/novo').padrao).toBe('/investimentos/ativos/novo');
  });
});

describe('posicionarBalao', () => {
  const janela = { largura: 1440, altura: 900 };
  const balao = { largura: 320, altura: 180 };
  const base = { janela, balao, topoLivre: 80, margem: 16, espaco: 12 };

  it('prefere abaixo do alvo, centralizado nele', () => {
    const alvo = { top: 200, left: 600, width: 200, height: 40, bottom: 240, right: 800 };

    expect(posicionarBalao({ ...base, alvo })).toEqual({ lado: 'abaixo', top: 252, left: 540 });
  });

  it('vai para cima quando não cabe abaixo', () => {
    const alvo = { top: 700, left: 600, width: 200, height: 40, bottom: 740, right: 800 };

    expect(posicionarBalao({ ...base, alvo })).toMatchObject({ lado: 'acima', top: 508 });
  });

  it('não sobe para trás do header fixo', () => {
    // Alvo alto ocupando quase a tela: nem abaixo nem acima cabem
    const alvo = { top: 120, left: 100, width: 900, height: 700, bottom: 820, right: 1000 };

    const posicao = posicionarBalao({ ...base, alvo });

    expect(posicao.lado).toBe('direita');
    expect(posicao.top).toBeGreaterThanOrEqual(80);
  });

  it('não sai pelas bordas laterais', () => {
    const alvo = { top: 200, left: 1380, width: 40, height: 40, bottom: 240, right: 1420 };

    expect(posicionarBalao({ ...base, alvo }).left).toBe(1440 - 16 - 320);
  });

  it('centraliza na tela quando não há alvo', () => {
    expect(posicionarBalao({ ...base, alvo: null })).toEqual({ lado: 'centro', top: 360, left: 560 });
  });
});

describe('passosDisponiveis', () => {
  it('mantém passos sem alvo e os de alvo presente, na ordem', () => {
    const passos = [{ titulo: 'a' }, { alvo: 'x', titulo: 'b' }, { alvo: 'y', titulo: 'c' }];

    expect(passosDisponiveis(passos, (id) => id === 'y').map((p) => p.titulo)).toEqual(['a', 'c']);
  });
});

describe('tours já vistos', () => {
  const armazenamento = () => {
    const dados = {};
    return {
      getItem: (k) => (k in dados ? dados[k] : null),
      setItem: (k, v) => {
        dados[k] = String(v);
      },
    };
  };

  it('lembra por padrão de rota', () => {
    const storage = armazenamento();

    expect(tourJaVisto('/backup', storage)).toBe(false);
    marcarTourVisto('/backup', storage);
    marcarTourVisto('/backup', storage);

    expect(tourJaVisto('/backup', storage)).toBe(true);
    expect(tourJaVisto('/metas', storage)).toBe(false);
  });

  it('trata armazenamento indisponível ou corrompido como nada visto, sem quebrar', () => {
    const quebrado = {
      getItem: () => {
        throw new Error('bloqueado');
      },
      setItem: () => {
        throw new Error('bloqueado');
      },
    };
    const lixo = { getItem: () => '{nao e json', setItem: () => {} };

    expect(tourJaVisto('/backup', quebrado)).toBe(false);
    expect(() => marcarTourVisto('/backup', quebrado)).not.toThrow();
    expect(tourJaVisto('/backup', lixo)).toBe(false);
  });
});
