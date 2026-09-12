/**
 * Calendário de Pagamentos e Recebimentos.
 *
 * Enquanto o Horizonte de Saldos responde "para onde meu saldo vai", esta tela responde
 * "o que acontece nesta semana" — e permite liquidar direto da célula do dia.
 *
 * Três decisões de leitura:
 *
 * **Grade em `<table>`, não em `<div>`.** Um mês é uma matriz de semanas por dias da
 * semana. Com `<div>`, quem usa leitor de tela perde a navegação por linha e coluna e a
 * associação com o cabeçalho.
 *
 * **Entrada e saída não se distinguem só por cor** (SC 1.4.1): cada valor traz o sinal
 * de mais ou menos, e o estado liquidado é texto, não apenas opacidade.
 *
 * **A compra de cartão aparece, mas não entra no total do dia.** Somá-la contaria o
 * mesmo dinheiro duas vezes, porque o desembolso real acontece na fatura.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RotateCcw,
} from 'lucide-react';

import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { useToast } from '../context/ToastContext';
import { extrairErros } from '../lib/apiErros';
import { formatarMoeda } from '../lib/moeda';
import {
  buscarCalendario,
  desfazerLiquidacao,
  liquidarLancamento,
} from '../services/planejamento';

// Segunda a domingo: o backend devolve `dia_semana_do_primeiro` na convenção do
// Python, em que segunda é 0.
const DIAS_DA_SEMANA = [
  { curto: 'Seg', longo: 'segunda-feira' },
  { curto: 'Ter', longo: 'terça-feira' },
  { curto: 'Qua', longo: 'quarta-feira' },
  { curto: 'Qui', longo: 'quinta-feira' },
  { curto: 'Sex', longo: 'sexta-feira' },
  { curto: 'Sáb', longo: 'sábado' },
  { curto: 'Dom', longo: 'domingo' },
];

const NOMES_DOS_MESES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

/**
 * Divide os dias do mês em semanas, preenchendo as bordas com vazios.
 *
 * @param {Array} dias - Dias devolvidos pelo servidor.
 * @param {number} deslocamento - Dia da semana do primeiro dia (segunda = 0).
 * @returns {Array<Array>} Matriz de semanas, cada uma com sete posições.
 */
function montarSemanas(dias, deslocamento) {
  const celulas = [...Array(deslocamento).fill(null), ...dias];
  while (celulas.length % 7 !== 0) {
    celulas.push(null);
  }

  const semanas = [];
  for (let i = 0; i < celulas.length; i += 7) {
    semanas.push(celulas.slice(i, i + 7));
  }
  return semanas;
}

export default function CalendarioPagamentos() {
  const hoje = new Date();
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth() + 1);
  const [diaAberto, setDiaAberto] = useState(null);

  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['planejamento', 'calendario', ano, mes],
    queryFn: () => buscarCalendario(ano, mes),
  });

  const mutacao = useMutation({
    mutationFn: ({ id, liquidar }) =>
      liquidar ? liquidarLancamento(id) : desfazerLiquidacao(id),
    onSuccess: (_, variaveis) => {
      // Invalida também o horizonte: liquidar move dinheiro entre o previsto e o
      // realizado, e a projeção parte exatamente dessa fronteira.
      queryClient.invalidateQueries({ queryKey: ['planejamento'] });
      addToast(
        variaveis.liquidar ? 'Lançamento liquidado.' : 'Liquidação desfeita.',
        'success'
      );
    },
    onError: (erro) => {
      const { geral } = extrairErros(erro, 'Não foi possível concluir a ação.');
      addToast(geral, 'error');
    },
  });

  const irParaMes = (delta) => {
    const referencia = new Date(ano, mes - 1 + delta, 1);
    setAno(referencia.getFullYear());
    setMes(referencia.getMonth() + 1);
  };

  const voltarParaHoje = () => {
    setAno(hoje.getFullYear());
    setMes(hoje.getMonth() + 1);
  };

  const detalhe = data?.dias.find((d) => d.dia === diaAberto) ?? null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Calendário de Pagamentos
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          O que vence e o que entra em cada dia. Clique num dia para liquidar os lançamentos.
        </p>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => irParaMes(-1)}
            className="h-9 w-9 rounded-xl p-0"
            aria-label="Mês anterior"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>

          {/* `role="status"` para que a troca de mês seja anunciada: o gatilho é
              um botão de seta, cujo rótulo não muda com a navegação. */}
          <p role="status" className="min-w-44 text-center text-sm font-semibold text-foreground">
            {NOMES_DOS_MESES[mes - 1]} de {ano}
          </p>

          <Button
            type="button"
            variant="outline"
            onClick={() => irParaMes(1)}
            className="h-9 w-9 rounded-xl p-0"
            aria-label="Próximo mês"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={voltarParaHoje}
          className="h-9 rounded-xl px-4 text-xs"
        >
          Ir para hoje
        </Button>
      </div>

      {isError && (
        <Alert variant="error" icon={AlertCircle}>
          <span className="font-medium">Não foi possível carregar o calendário.</span>
        </Alert>
      )}

      {isLoading ? (
        <div role="status" className="flex flex-col items-center gap-3 py-16">
          <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">Carregando o mês...</p>
        </div>
      ) : (
        data && (
          <Card className="overflow-hidden rounded-2xl border-border/40">
            <CardContent className="p-3">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[44rem] border-separate border-spacing-1">
                  <caption className="sr-only">
                    Pagamentos e recebimentos de {NOMES_DOS_MESES[mes - 1]} de {ano}
                  </caption>
                  <thead>
                    <tr>
                      {DIAS_DA_SEMANA.map((dia) => (
                        <th
                          key={dia.curto}
                          scope="col"
                          className="px-2 py-2 text-center text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                        >
                          <span aria-hidden="true">{dia.curto}</span>
                          <span className="sr-only">{dia.longo}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {montarSemanas(data.dias, data.dia_semana_do_primeiro).map(
                      (semana, indiceSemana) => (
                        <tr key={indiceSemana}>
                          {semana.map((dia, indiceDia) => {
                            if (!dia) {
                              return <td key={indiceDia} className="p-1" />;
                            }

                            const temMovimento = dia.lancamentos.length > 0;
                            return (
                              <td key={indiceDia} className="p-1 align-top">
                                <button
                                  type="button"
                                  onClick={() => setDiaAberto(dia.dia)}
                                  disabled={!temMovimento}
                                  className={`flex h-24 w-full flex-col gap-1 rounded-xl border p-2 text-left transition-colors ${
                                    dia.eh_hoje
                                      ? 'border-primary ring-1 ring-primary'
                                      : 'border-border/50'
                                  } ${
                                    temMovimento
                                      ? 'hover:bg-muted'
                                      : 'cursor-default opacity-60'
                                  }`}
                                >
                                  <span className="text-xs font-semibold tabular-nums text-foreground">
                                    {dia.dia}
                                    {dia.eh_hoje && (
                                      <span className="ml-1 text-[0.65rem] font-medium text-primary">
                                        hoje
                                      </span>
                                    )}
                                  </span>

                                  {Number(dia.total_receitas) > 0 && (
                                    <span className="text-[0.7rem] font-medium tabular-nums text-emerald-800 dark:text-emerald-300">
                                      + {formatarMoeda(dia.total_receitas)}
                                    </span>
                                  )}
                                  {Number(dia.total_despesas) > 0 && (
                                    <span className="text-[0.7rem] font-medium tabular-nums text-red-700 dark:text-red-300">
                                      − {formatarMoeda(dia.total_despesas)}
                                    </span>
                                  )}

                                  {dia.pendentes > 0 && (
                                    <span className="mt-auto text-[0.65rem] text-muted-foreground">
                                      {dia.pendentes}{' '}
                                      {dia.pendentes === 1 ? 'pendente' : 'pendentes'}
                                    </span>
                                  )}
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )
      )}

      <Modal
        isOpen={Boolean(detalhe)}
        onClose={() => setDiaAberto(null)}
        title={
          detalhe
            ? `${detalhe.dia} de ${NOMES_DOS_MESES[mes - 1]} de ${ano}`
            : ''
        }
        description={
          detalhe
            ? `${detalhe.lancamentos.length} lançamento${
                detalhe.lancamentos.length === 1 ? '' : 's'
              } neste dia`
            : undefined
        }
        size="md"
      >
        <ul className="divide-y divide-border/40">
          {detalhe?.lancamentos.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{item.descricao}</p>
                <p className="text-xs text-muted-foreground">
                  {item.categoria || 'Sem categoria'}
                  {item.cartao && ` · ${item.cartao}`}
                  {item.eh_fatura_cartao && ' · fatura'}
                  {item.recorrente && ' · recorrente'}
                  {/* Estado em texto, não só na opacidade do item. */}
                  {item.realizado ? ' · liquidado' : ' · pendente'}
                </p>
              </div>

              <div className="flex shrink-0 flex-col items-end gap-1.5">
                <span
                  className={`text-sm font-semibold tabular-nums ${
                    item.tipo === 'R'
                      ? 'text-emerald-800 dark:text-emerald-300'
                      : 'text-red-700 dark:text-red-300'
                  }`}
                >
                  {item.tipo === 'R' ? '+' : '−'} {formatarMoeda(item.valor)}
                </span>

                {/* Rótulo VISÍVEL, não apenas ícone com `aria-label`.
                    Um nome acessível responde ao leitor de tela, não a quem está
                    olhando a tela — e "o que este ícone faz?" é uma pergunta
                    visual. O verbo muda conforme o tipo porque "pago" não descreve
                    o recebimento de uma receita.

                    O nome acessível é composto por CONTEÚDO (texto visível + um
                    complemento `sr-only`), e não por `aria-label`: assim o texto
                    visível é prefixo literal do nome acessível, e quem usa comando
                    de voz e diz "clique Marcar como pago" acerta (SC 2.5.3).
                    Mesmo padrão já adotado no controle de tema. */}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    mutacao.mutate({ id: item.id, liquidar: !item.realizado })
                  }
                  disabled={mutacao.isPending}
                  className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs"
                >
                  {item.realizado ? (
                    <>
                      <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                      {item.tipo === 'R' ? 'Desfazer recebimento' : 'Desfazer pagamento'}
                      <span className="sr-only"> de {item.descricao}</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                      {item.tipo === 'R' ? 'Marcar como recebido' : 'Marcar como pago'}
                      <span className="sr-only"> — {item.descricao}</span>
                    </>
                  )}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </Modal>
    </div>
  );
}
