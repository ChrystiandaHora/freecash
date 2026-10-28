/**
 * Explicação de um sinal: o que fazer, quanto, e como fica a isenção de IR.
 *
 * Os textos vêm de lib/sinais.js; aqui só se liga o formatador ao olho de privacidade.
 */
import { useMoeda } from '../../hooks/useMoeda';
import { textoAcao, textoIsencao } from '../../lib/sinais';
import { SinalBadge } from './SinalBadge';

/**
 * @param {Object} props
 * @param {Object} props.sinal - Sinal com `meta_porcentagem` preenchida.
 * @param {React.ReactNode} [props.titulo] - Ticker e carteira, quando o contexto não os mostra.
 */
export function SinalResumo({ sinal, titulo }) {
  const { formatarMoeda } = useMoeda();
  const acao = textoAcao(sinal, formatarMoeda);
  if (!acao) return null;
  const isencao = textoIsencao(sinal);

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {titulo}
        <SinalBadge sinal={sinal} />
      </div>
      <p className="text-xs text-foreground">{acao}</p>
      {isencao && <p className="text-xs text-muted-foreground">{isencao}</p>}
    </div>
  );
}
