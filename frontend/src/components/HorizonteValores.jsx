/**
 * Valores monetários com sinal, usados na composição do Horizonte de Saldos.
 *
 * Entrada e saída levam sinal em texto (+ e −) além da cor, para não depender só
 * dela (SC 1.4.1).
 */
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';

import { formatarMoeda } from '../lib/moeda';

export const COR_ENTRADA = 'text-emerald-800 dark:text-emerald-300';
export const COR_SAIDA = 'text-red-700 dark:text-red-300';

/**
 * Valor com sinal explícito.
 *
 * @param {number|string} props.valor - Valor absoluto.
 * @param {'+'|'−'} props.sinal - Sinal a exibir.
 */
export function ValorComSinal({ valor, sinal }) {
  return (
    <span className={`tabular-nums ${sinal === '+' ? COR_ENTRADA : COR_SAIDA}`}>
      {sinal} {formatarMoeda(valor)}
    </span>
  );
}

/**
 * Variação de um período, com seta e palavra além da cor.
 *
 * @param {number} props.valor - Diferença entre o fim e o início do período.
 */
export function Variacao({ valor }) {
  if (Math.abs(valor) < 0.005) {
    return <span className="tabular-nums text-muted-foreground">sem variação</span>;
  }
  const subiu = valor > 0;
  const Icone = subiu ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-1 tabular-nums ${subiu ? COR_ENTRADA : COR_SAIDA}`}>
      <Icone className="h-3.5 w-3.5" aria-hidden="true" />
      {subiu ? '+' : '−'} {formatarMoeda(Math.abs(valor))}
      <span className="sr-only">{subiu ? ', aumento' : ', queda'}</span>
    </span>
  );
}
