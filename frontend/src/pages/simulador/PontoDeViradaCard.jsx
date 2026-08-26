import { useId, useState } from 'react';
import { AlertCircle, ShieldCheck, ChevronDown, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { formatCurrency, formatDateLong } from './formatters';

/**
 * "Ponto de virada": um resumo de uma frase, sempre visível, com um botão
 * "Ver detalhes" que revela o diagnóstico completo (datas, margem necessária,
 * disclaimer sobre caixa). O resumo já responde a pergunta central; os
 * detalhes ficam a um clique para quem quiser o cálculo por extenso.
 */
export default function PontoDeViradaCard({ pontoDeVirada, projecaoCarregando }) {
  const [expandido, setExpandido] = useState(false);
  const detalhesId = useId();

  const emVermelho = Boolean(pontoDeVirada?.primeiroVermelho);

  return (
    <Card
      className={
        emVermelho
          ? 'border-red-600/40 bg-red-500/5 dark:border-red-400/40'
          : 'border-emerald-600/40 bg-emerald-500/5 dark:border-emerald-400/40'
      }
    >
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          {emVermelho ? (
            <AlertCircle
              className="h-5 w-5 shrink-0 text-red-600 dark:text-red-400"
              aria-hidden="true"
            />
          ) : (
            <ShieldCheck
              className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400"
              aria-hidden="true"
            />
          )}
          <h2 className="text-lg font-semibold leading-none tracking-tight text-foreground">
            Ponto de virada
          </h2>
        </div>
      </CardHeader>

      <CardContent>
        <div aria-live="polite" className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-base text-foreground">
            {projecaoCarregando ? (
              <span className="text-muted-foreground">Calculando o ponto de virada...</span>
            ) : !pontoDeVirada ? (
              <span className="text-muted-foreground">
                Sem lançamentos suficientes para projetar o horizonte.
              </span>
            ) : emVermelho ? (
              <>
                Suas saídas passam as entradas em{' '}
                <strong className="font-semibold text-red-600 dark:text-red-400">
                  {formatDateLong(pontoDeVirada.primeiroVermelho.date)}
                </strong>{' '}
                — {pontoDeVirada.diasNoVermelho}{' '}
                {pontoDeVirada.diasNoVermelho === 1 ? 'dia no vermelho' : 'dias no vermelho'}.
              </>
            ) : (
              <>
                Suas entradas cobrem as saídas até{' '}
                <strong className="font-semibold text-emerald-600 dark:text-emerald-400">
                  {formatDateLong(pontoDeVirada.fimHorizonte)}
                </strong>
                .
              </>
            )}
          </p>

          {!projecaoCarregando && pontoDeVirada && (
            <Button
              variant="outline"
              size="sm"
              aria-expanded={expandido}
              aria-controls={detalhesId}
              onClick={() => setExpandido((v) => !v)}
              className="flex shrink-0 items-center gap-1.5"
            >
              {expandido ? 'Ocultar detalhes' : 'Ver detalhes'}
              <ChevronDown
                className={`h-4 w-4 transition-transform ${expandido ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </Button>
          )}
        </div>

        {!projecaoCarregando && pontoDeVirada && expandido && (
          <div id={detalhesId} className="mt-4 space-y-3 border-t border-border pt-4 text-sm">
            {emVermelho ? (
              <>
                {pontoDeVirada.dataLimite ? (
                  <p className="text-base text-foreground">
                    Para atravessar o horizonte até{' '}
                    <strong className="font-semibold">
                      {formatDateLong(pontoDeVirada.fimHorizonte)}
                    </strong>{' '}
                    sem recorrer a reserva, você precisa de{' '}
                    <strong className="font-semibold">
                      {formatCurrency(pontoDeVirada.margemNecessaria)}
                    </strong>{' '}
                    até{' '}
                    <strong className="font-semibold">
                      {formatDateLong(pontoDeVirada.dataLimite)}
                    </strong>
                    .
                  </p>
                ) : (
                  <p className="text-base text-foreground">
                    O fluxo já entra negativo hoje: não sobrou prazo para agir antes.
                    Atravessar o horizonte até{' '}
                    <strong className="font-semibold">
                      {formatDateLong(pontoDeVirada.fimHorizonte)}
                    </strong>{' '}
                    exige{' '}
                    <strong className="font-semibold">
                      {formatCurrency(pontoDeVirada.margemNecessaria)}
                    </strong>{' '}
                    agora.
                  </p>
                )}

                <p className="text-muted-foreground">
                  O pior momento é{' '}
                  <strong className="font-semibold text-red-600 dark:text-red-400">
                    {formatCurrency(pontoDeVirada.pior.acumulado)}
                  </strong>{' '}
                  em {formatDateLong(pontoDeVirada.pior.date)}.
                </p>

                {pontoDeVirada.principaisDespesas?.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Contas que empurram para o vermelho, até {formatDateLong(pontoDeVirada.pior.date)}
                    </p>
                    <ul className="space-y-1.5">
                      {pontoDeVirada.principaisDespesas.map((despesa) => (
                        <li
                          key={`${despesa.simulado ? 'sim' : 'real'}-${despesa.descricao}`}
                          className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/30 px-3 py-1.5 text-xs"
                        >
                          <span className="flex min-w-0 items-center gap-1.5 text-foreground">
                            {despesa.simulado && (
                              <Sparkles className="h-3 w-3 shrink-0 text-amber-500" aria-hidden="true" />
                            )}
                            <span className="truncate">{despesa.descricao}</span>
                            {despesa.ocorrencias > 1 && (
                              <Badge variant="secondary" className="shrink-0 px-1.5 py-0 text-[10px]">
                                {despesa.ocorrencias}x
                              </Badge>
                            )}
                          </span>
                          <span className="shrink-0 font-semibold text-red-600 dark:text-red-400">
                            {formatCurrency(despesa.total)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              pontoDeVirada.folgaMinima && (
                <p className="text-muted-foreground">
                  No dia mais apertado o acumulado ainda é de{' '}
                  <strong className="font-semibold text-foreground">
                    {formatCurrency(pontoDeVirada.folgaMinima.acumulado)}
                  </strong>{' '}
                  ({formatDateLong(pontoDeVirada.folgaMinima.date)}).
                </p>
              )
            )}

            {/* Nota permanente, não um aviso de falha: por decisão de produto o card
                mede fluxo, e ignorar o caixa é o ponto — é assim que um mês
                estruturalmente no vermelho aparece mesmo com reserva sobrando. */}
            <p className="border-t border-border pt-3 text-xs text-muted-foreground">
              Este diagnóstico ignora o seu saldo em caixa: mede só o fluxo acumulado de hoje
              em diante. O saldo projetado com o caixa incluído está na tabela de projeção
              mensal.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
