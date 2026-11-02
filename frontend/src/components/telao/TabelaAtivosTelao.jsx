/**
 * Tabela das maiores posições no telão, com a variação do dia.
 *
 * Mostra só as linhas que cabem inteiras na altura disponível (ver `useQuantosCabem`):
 * sem rolagem nem rotação automática de páginas, que num telão exigiriam controle de
 * pausa (WCAG 2.2.2). As que não cabem ficam `invisible`, fora da árvore de
 * acessibilidade, e são contadas no rodapé. A variação traz ícone e sinal no texto, não
 * só cor.
 *
 * A área medida é `relative` de propósito: sem isso, os textos `sr-only` (absolutos) das
 * linhas escondidas escapam do `overflow-hidden` e fazem a página rolar.
 */
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { useMoeda } from '../../hooks/useMoeda';
import { useQuantosCabem } from '../../hooks/useQuantosCabem';
import { formatarMoeda as formatarCotacao } from '../../lib/moeda';
import { apresentarVariacao } from '../../lib/telao';

const PESO = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

const ESTILO_VARIACAO = {
  alta: { Icone: ArrowUpRight, classe: 'text-emerald-700 dark:text-emerald-400', rotulo: 'alta' },
  baixa: { Icone: ArrowDownRight, classe: 'text-rose-700 dark:text-rose-400', rotulo: 'baixa' },
  estavel: { Icone: Minus, classe: 'text-muted-foreground', rotulo: 'estável' },
};

function Variacao({ pct }) {
  const variacao = apresentarVariacao(pct);
  if (!variacao) return <span className="text-muted-foreground">—</span>;
  const { Icone, classe, rotulo } = ESTILO_VARIACAO[variacao.sentido];
  return (
    <span className={`inline-flex items-center justify-end gap-[0.25em] font-bold ${classe}`}>
      <Icone className="h-[1em] w-[1em]" aria-hidden="true" />
      <span className="sr-only">{rotulo} de </span>
      {variacao.texto}
    </span>
  );
}

/**
 * @param {Object} props
 * @param {Array<Object>} props.ativos - Linhas de `/api/investimentos/telao/`, já ordenadas.
 * @param {string} [props.className]
 */
export function TabelaAtivosTelao({ ativos, className = '' }) {
  const { formatarMoeda } = useMoeda();
  const lista = ativos ?? [];
  const [areaRef, quantos] = useQuantosCabem(lista.length);
  const restantes = lista.length - quantos;

  return (
    <section
      aria-labelledby="telao-ativos-titulo"
      className={`flex min-h-0 flex-col rounded-2xl border border-border/60 bg-card px-[1.1em] pb-[0.6em] pt-[0.9em] ${className}`}
    >
      <h2 id="telao-ativos-titulo" className="mb-[0.4em] text-[0.7em] font-bold uppercase tracking-[0.15em] text-muted-foreground">
        Maiores posições
      </h2>

      {lista.length === 0 ? (
        <p className="py-[2em] text-center text-muted-foreground">Nenhuma posição aberta neste escopo.</p>
      ) : (
        <div ref={areaRef} className="relative overflow-x-auto lg:min-h-0 lg:flex-1 lg:overflow-hidden">
          <table className="w-full text-left text-[0.9em] tabular-nums sm:text-[1em]">
            <thead>
              <tr className="border-b border-border/60 text-[0.7em] uppercase tracking-wider text-muted-foreground">
                <th scope="col" className="py-[0.5em] pr-[0.6em] sm:pr-[1em] font-semibold">Ativo</th>
                <th scope="col" className="hidden py-[0.5em] pr-[0.6em] sm:pr-[1em] text-right font-semibold sm:table-cell">Cotação</th>
                <th scope="col" className="py-[0.5em] pr-[0.6em] sm:pr-[1em] text-right font-semibold">Dia</th>
                <th scope="col" className="py-[0.5em] pr-[0.6em] sm:pr-[1em] text-right font-semibold">Posição</th>
                <th scope="col" className="hidden py-[0.5em] text-right font-semibold sm:table-cell">Peso</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {lista.map((ativo, idx) => {
                const escondido = idx >= quantos;
                return (
                  <tr key={ativo.id} data-cabe="" className={escondido ? 'invisible' : undefined} aria-hidden={escondido || undefined}>
                    <th scope="row" className="py-[0.4em] pr-[0.6em] sm:pr-[1em] font-normal">
                      <span className="block font-extrabold leading-tight text-foreground">{ativo.ticker}</span>
                      {/* Subtítulo sempre presente: linhas de altura igual medem de forma previsível */}
                      <span className="block max-w-[12ch] truncate sm:max-w-[24ch] text-[0.72em] leading-tight text-muted-foreground">
                        {ativo.nome || ' '}
                      </span>
                    </th>
                    <td className="hidden py-[0.4em] pr-[0.6em] sm:pr-[1em] text-right text-foreground sm:table-cell">
                      {ativo.cotacao === null ? '—' : formatarCotacao(ativo.cotacao)}
                    </td>
                    <td className="py-[0.4em] pr-[0.6em] sm:pr-[1em] text-right">
                      <Variacao pct={ativo.variacao_dia_pct} />
                    </td>
                    <td className="py-[0.4em] pr-[0.6em] sm:pr-[1em] text-right font-semibold text-foreground">{formatarMoeda(ativo.valor)}</td>
                    <td className="hidden py-[0.4em] text-right text-muted-foreground sm:table-cell">{PESO.format(ativo.peso_pct)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* A linha existe sempre: aparecer só com sobra mudaria a altura e a conta */}
      <p className="mt-[0.3em] min-h-[1.5em] text-[0.8em] text-muted-foreground">
        {restantes > 0 && `e mais ${restantes} ${restantes === 1 ? 'ativo' : 'ativos'} com posição menor`}
      </p>
    </section>
  );
}
