/**
 * Linha de indicadores do telão, lidos de `/api/investimentos/dashboard/`.
 *
 * O patrimônio ganha o dobro da largura: é o número que se procura de longe. Lucro e
 * rentabilidade trazem o sinal no texto, além da cor. Tamanhos em `em`, relativos à
 * fonte-base do telão.
 */
import { useMoeda } from '../../hooks/useMoeda';

const PERCENTUAL = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
});

const tomDoResultado = (valor) =>
  valor >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400';

function Indicador({ rotulo, valor, detalhe, destaque = false, tom = 'text-foreground' }) {
  return (
    <div
      className={`flex min-w-0 flex-col justify-between gap-[0.5em] rounded-2xl border border-border/60 bg-card px-[1.1em] py-[0.9em] ${
        destaque ? 'col-span-2' : ''
      }`}
    >
      <dt className="text-[0.7em] font-bold uppercase tracking-[0.15em] text-muted-foreground">{rotulo}</dt>
      <dd className="min-w-0">
        <span
          className={`block truncate font-black leading-none tabular-nums tracking-tight ${tom} ${
            destaque ? 'text-[2.4em] lg:text-[3.1em]' : 'text-[1.6em] lg:text-[2.1em]'
          }`}
        >
          {valor}
        </span>
        {detalhe && <span className="mt-[0.35em] block text-[0.85em] text-muted-foreground">{detalhe}</span>}
      </dd>
    </div>
  );
}

/**
 * @param {Object} props
 * @param {Object} props.dados - Payload do dashboard de investimentos.
 */
export function KpisTelao({ dados }) {
  const { formatarMoeda } = useMoeda();
  const {
    total_patrimonio = 0,
    total_investido = 0,
    total_rentabilidade = 0,
    total_rentabilidade_percentual = 0,
    total_dividendos = 0,
  } = dados ?? {};

  return (
    <dl aria-label="Resumo do patrimônio" className="grid shrink-0 grid-cols-2 gap-[1em] lg:grid-cols-5">
      <Indicador
        destaque
        rotulo="Patrimônio a mercado"
        valor={formatarMoeda(total_patrimonio)}
        detalhe={`Investido: ${formatarMoeda(total_investido)}`}
      />
      <Indicador rotulo="Lucro total" valor={formatarMoeda(total_rentabilidade)} tom={tomDoResultado(total_rentabilidade)} />
      <Indicador rotulo="Proventos" valor={formatarMoeda(total_dividendos)} />
      <Indicador
        rotulo="Rentabilidade"
        valor={`${PERCENTUAL.format(total_rentabilidade_percentual)}%`}
        tom={tomDoResultado(total_rentabilidade_percentual)}
      />
    </dl>
  );
}
