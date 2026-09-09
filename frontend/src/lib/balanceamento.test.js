/**
 * Teste tabelado de qual carteira o balanceamento abre.
 *
 * Um caso por estado real de seleção. É o seguro contra o beco sem saída que a tela
 * já teve: pedir "selecione uma carteira" numa situação em que o seletor não é
 * renderizado, ou em que a seleção salva não vale mais.
 *
 * Não precisa de jsdom nem de @testing-library — `lib/balanceamento.js` é puro.
 */
import { describe, expect, it } from 'vitest';
import { resolverCarteiraEmFoco } from './balanceamento';

const UMA = [{ id: 7 }];
const DUAS = [{ id: 7 }, { id: 9 }];

describe('resolverCarteiraEmFoco', () => {
  /** [caso, params, esperado] */
  const CASOS = [
    [
      'carteira escolhida vence tudo',
      { carteiraId: 9, consolidadoExplicito: false, carteirasAtivas: DUAS },
      9,
    ],
    [
      'primeira visita com duas carteiras abre na primeira, não no consolidado',
      { carteiraId: null, consolidadoExplicito: false, carteirasAtivas: DUAS },
      7,
    ],
    [
      'primeira visita com uma carteira abre nela',
      { carteiraId: null, consolidadoExplicito: false, carteirasAtivas: UMA },
      7,
    ],
    [
      'consolidado pedido no seletor é respeitado',
      { carteiraId: null, consolidadoExplicito: true, carteirasAtivas: DUAS },
      null,
    ],
    [
      'consolidado pedido com uma carteira só é ignorado: o seletor não aparece',
      { carteiraId: null, consolidadoExplicito: true, carteirasAtivas: UMA },
      7,
    ],
    [
      'carteira salva que foi arquivada cai na primeira ativa, não no consolidado',
      { carteiraId: null, consolidadoExplicito: false, carteirasAtivas: DUAS },
      7,
    ],
    [
      'sem carteira ativa nenhuma não há o que focar',
      { carteiraId: null, consolidadoExplicito: false, carteirasAtivas: [] },
      null,
    ],
    [
      'consolidado pedido sem carteira ativa nenhuma também não inventa foco',
      { carteiraId: null, consolidadoExplicito: true, carteirasAtivas: [] },
      null,
    ],
  ];

  it.each(CASOS)('%s', (_caso, params, esperado) => {
    expect(resolverCarteiraEmFoco(params)).toBe(esperado);
  });

  it('não explode sem a lista de carteiras', () => {
    expect(resolverCarteiraEmFoco({ carteiraId: null, consolidadoExplicito: false })).toBeNull();
  });
});
