/**
 * Contrato do conteúdo dos tours, para todas as rotas de uma vez.
 *
 * O tour pula em silêncio o passo cujo alvo não está na tela — é o comportamento
 * certo para uma lista vazia, e o errado para um `alvo` digitado diferente do
 * `data-tour` da página. Este teste separa os dois casos: o alvo precisa existir no
 * código-fonte, mesmo que nem sempre esteja na tela.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { tours } from './index';

const RAIZ = join(import.meta.dirname, '..', '..');
const MAX_TITULO = 40;
const MAX_TEXTO = 200;

function arquivosDeCodigo(dir) {
  return readdirSync(dir).flatMap((nome) => {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) return arquivosDeCodigo(caminho);
    return /\.jsx?$/.test(nome) && !/\.test\.js$/.test(nome) ? [caminho] : [];
  });
}

const codigo = arquivosDeCodigo(RAIZ).map((arquivo) => readFileSync(arquivo, 'utf8')).join('\n');
const alvosNoCodigo = new Set([...codigo.matchAll(/data-tour=["']([^"']+)["']/g)].map((m) => m[1]));
const rotasDoApp = new Set(
  [...readFileSync(join(RAIZ, 'App.jsx'), 'utf8').matchAll(/<Route\s+path="([^"]+)"/g)].map((m) => `/${m[1]}`),
);

describe.each(Object.entries(tours))('tour de %s', (rota, passos) => {
  it('pertence a uma rota que existe no app', () => {
    expect(rotasDoApp.has(rota)).toBe(true);
  });

  it('tem de 3 a 8 passos e abre apresentando a tela, sem alvo', () => {
    expect(passos.length).toBeGreaterThanOrEqual(3);
    expect(passos.length).toBeLessThanOrEqual(8);
    expect(passos[0].alvo).toBeUndefined();
  });

  it('aponta só para alvos que existem no código, sem repetir', () => {
    const alvos = passos.filter((p) => p.alvo).map((p) => p.alvo);
    expect(alvos.filter((alvo) => !alvosNoCodigo.has(alvo))).toEqual([]);
    expect(new Set(alvos).size).toBe(alvos.length);
  });

  it('tem textos curtos', () => {
    for (const { titulo, texto } of passos) {
      expect(titulo.length, titulo).toBeLessThanOrEqual(MAX_TITULO);
      expect(texto.length, texto).toBeLessThanOrEqual(MAX_TEXTO);
    }
  });
});
