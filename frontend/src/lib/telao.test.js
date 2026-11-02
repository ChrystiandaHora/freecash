import { describe, expect, it } from 'vitest';

import {
  ATRASO_MINIMO_MS,
  FOLGA_MS,
  INTERVALO_SINCRONIZACAO_MS,
  STATUS_SINCRONIZACAO,
  apresentarVariacao,
  calcularAtrasoProximaSincronizacao,
  formatarAtualizacao,
  formatarContagem,
  contarQueCabem,
  rotuloStatus,
} from './telao';

const AGORA = Date.parse('2026-11-04T17:00:00Z');
const minutos = (n) => n * 60 * 1000;

describe('calcularAtrasoProximaSincronizacao', () => {
  it('segue o proxima_em do servidor com a folga', () => {
    const proximaEm = new Date(AGORA + minutos(10)).toISOString();
    expect(calcularAtrasoProximaSincronizacao(proximaEm, AGORA)).toBe(minutos(10) + FOLGA_MS);
  });

  it('não deixa um proxima_em no passado virar laço', () => {
    const proximaEm = new Date(AGORA - minutos(3)).toISOString();
    expect(calcularAtrasoProximaSincronizacao(proximaEm, AGORA)).toBe(ATRASO_MINIMO_MS);
  });

  it('limita a espera a um intervalo, mesmo com o pregão fechado até amanhã', () => {
    const proximaEm = new Date(AGORA + minutos(60 * 16)).toISOString();
    expect(calcularAtrasoProximaSincronizacao(proximaEm, AGORA)).toBe(INTERVALO_SINCRONIZACAO_MS);
  });

  it('cai no intervalo padrão sem resposta do servidor', () => {
    expect(calcularAtrasoProximaSincronizacao(undefined, AGORA)).toBe(INTERVALO_SINCRONIZACAO_MS);
    expect(calcularAtrasoProximaSincronizacao('lixo', AGORA)).toBe(INTERVALO_SINCRONIZACAO_MS);
  });
});

describe('formatarContagem', () => {
  it('mostra minutos e segundos com dois dígitos', () => {
    expect(formatarContagem(minutos(12) + 3000)).toBe('12:03');
  });

  it('arredonda para cima o segundo em curso', () => {
    expect(formatarContagem(1500)).toBe('00:02');
  });

  it('não fica negativa', () => {
    expect(formatarContagem(-5000)).toBe('00:00');
  });
});

describe('formatarAtualizacao', () => {
  it('devolve null sem instante', () => {
    expect(formatarAtualizacao(null, AGORA)).toBeNull();
    expect(formatarAtualizacao('', AGORA)).toBeNull();
  });

  it('mostra só a hora quando a cotação é de hoje', () => {
    expect(formatarAtualizacao(new Date(AGORA - minutos(5)).toISOString(), AGORA)).toMatch(/^\d{2}:\d{2}$/);
  });

  it('acrescenta o dia quando a cotação não é de hoje', () => {
    const tresDiasAntes = new Date(AGORA - minutos(60 * 24 * 3)).toISOString();
    expect(formatarAtualizacao(tresDiasAntes, AGORA)).toMatch(/^\d{2}\/\d{2}, \d{2}:\d{2}$/);
  });
});

describe('rotuloStatus', () => {
  it('traduz cada status da sincronização', () => {
    expect(rotuloStatus(STATUS_SINCRONIZACAO.ATUALIZADO)).toBe('Pregão aberto');
    expect(rotuloStatus(STATUS_SINCRONIZACAO.EM_CACHE)).toBe('Pregão aberto');
    expect(rotuloStatus(STATUS_SINCRONIZACAO.FORA_DO_PREGAO)).toBe('Pregão fechado');
    expect(rotuloStatus(STATUS_SINCRONIZACAO.LIMITADO)).toMatch(/pausa/);
    expect(rotuloStatus(STATUS_SINCRONIZACAO.FALHOU)).toMatch(/indisponível/);
  });

  it('não inventa rótulo para status desconhecido', () => {
    expect(rotuloStatus('outro')).toBeNull();
    expect(rotuloStatus(undefined)).toBeNull();
  });
});

describe('apresentarVariacao', () => {
  it('marca alta com sinal explícito', () => {
    expect(apresentarVariacao(1.234)).toEqual({ texto: '+1,23%', sentido: 'alta' });
  });

  it('marca baixa', () => {
    expect(apresentarVariacao(-5)).toEqual({ texto: '-5,00%', sentido: 'baixa' });
  });

  it('trata variação que arredonda para zero como estável', () => {
    expect(apresentarVariacao(0.001)).toEqual({ texto: '0,00%', sentido: 'estavel' });
  });

  it('devolve null sem pregão anterior', () => {
    expect(apresentarVariacao(null)).toBeNull();
    expect(apresentarVariacao(undefined)).toBeNull();
  });
});

describe('contarQueCabem', () => {
  it('conta os itens inteiros acima da borda', () => {
    expect(contarQueCabem([40, 80, 120, 160], 130)).toBe(3);
  });

  it('para no primeiro que não cabe, sem deixar buraco', () => {
    expect(contarQueCabem([40, 200, 80], 130)).toBe(1);
  });

  it('tolera meio pixel de arredondamento', () => {
    expect(contarQueCabem([100.4], 100)).toBe(1);
    expect(contarQueCabem([101], 100)).toBe(0);
  });

  it('com tudo cabendo, devolve todos', () => {
    expect(contarQueCabem([10, 20], 500)).toBe(2);
    expect(contarQueCabem([], 500)).toBe(0);
  });
});
