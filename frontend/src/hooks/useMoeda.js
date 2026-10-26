/**
 * Formatadores monetários já ligados ao olho de "ocultar valores".
 *
 * É a porta de entrada das telas para formatar dinheiro: com o modo ligado, todo valor
 * vira a máscara de `lib/moeda.js`. Quem monta opções de gráfico deve pôr
 * `valoresOcultos` na `key` do `<Chart>`, porque o ApexCharts não relê os formatadores
 * sozinho.
 */
import { useMemo } from 'react';
import { usePrivacidade } from '../context/PrivacidadeProvider';
import { formatarMoeda, formatarMoedaCompacta } from '../lib/moeda';

/**
 * @returns {{
 *   formatarMoeda: (valor: number|string) => string,
 *   formatarMoedaCompacta: (valor: number|string) => string,
 *   valoresOcultos: boolean,
 * }}
 */
export function useMoeda() {
  const { valoresOcultos } = usePrivacidade();

  return useMemo(
    () => ({
      formatarMoeda: (valor) => formatarMoeda(valor, { ocultar: valoresOcultos }),
      formatarMoedaCompacta: (valor) => formatarMoedaCompacta(valor, { ocultar: valoresOcultos }),
      valoresOcultos,
    }),
    [valoresOcultos]
  );
}
