/**
 * Horizonte de Saldos — projeção do saldo acumulado, dia a dia, por 12 meses.
 *
 * Responde *em que dia meu saldo fica negativo?* — o dashboard mostra só o mês corrente
 * e o simulador trabalha com cenários em memória. Aqui a curva sai dos lançamentos
 * reais, incluindo as ocorrências futuras das regras recorrentes.
 *
 * Três decisões de leitura:
 *
 * **A situação do dia não é comunicada só por cor** (SC 1.4.1), o que numa grade de ~370
 * células é fácil de esquecer. Cada célula tem cor de fundo, borda esquerda com
 * espessura própria por situação e um texto `sr-only` com a palavra — além do sinal de
 * menos no saldo negativo.
 *
 * **O detalhe do dia reusa `/api/planejamento/calendario/`.** Um endpoint só para isso
 * duplicaria a regra de qual lançamento entra na conta.
 *
 * **Metas são um cenário, não a projeção.** O aporte planejado é intenção de poupar;
 * misturá-lo à curva principal faria o usuário ler como dívida algo que pode desfazer.
 *
 * **O investido fica fora por padrão.** Dinheiro aplicado não paga conta, e mantê-lo no
 * saldo esconde aperto de caixa — somá-lo de volta é que precisa ser pedido. Vai como
 * parâmetro ao servidor, e não como série paralela: é deslocamento constante da âncora,
 * e cruzá-lo com o cenário de metas geraria quatro séries para duas perguntas. Refazendo
 * a busca, a classificação de cada dia continua vindo pronta de lá.
 */
import { useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, AlertTriangle, CalendarClock, Loader2, Target, Wallet } from 'lucide-react';

import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { formatarMoeda, formatarMoedaCompacta } from '../lib/moeda';
import { buscarCalendario, buscarHorizonteSaldos } from '../services/planejamento';

const DIAS_DO_MES = Array.from({ length: 31 }, (_, i) => i + 1);

/**
 * Classes visuais de cada situação de saldo.
 *
 * A borda esquerda é o sinal não-cromático: ela sobrevive à escala de cinza, ao
 * daltonismo e ao modo de cores forçadas, onde as cores de fundo são substituídas
 * pela paleta do sistema operacional.
 */
const ESTILO_POR_SITUACAO = {
  negativo: {
    celula: 'border-l-[3px] border-l-red-600 bg-red-500/10 text-red-700 dark:text-red-300',
    rotulo: 'negativo',
  },
  atencao: {
    celula: 'border-l-[3px] border-l-amber-600 border-dashed bg-amber-500/10 text-amber-800 dark:text-amber-300',
    rotulo: 'abaixo do limite de atenção',
  },
  confortavel: {
    celula: 'border-l-[3px] border-l-transparent bg-emerald-500/5 text-emerald-800 dark:text-emerald-300',
    rotulo: 'acima do limite de atenção',
  },
};

/**
 * Formata uma data ISO por extenso, em português.
 *
 * @param {string} iso - Data no formato AAAA-MM-DD.
 * @returns {string} Data legível.
 */
function dataPorExtenso(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

/**
 * Item da legenda, com o mesmo tratamento de borda usado nas células.
 *
 * @param {string} props.situacao - Chave em `ESTILO_POR_SITUACAO`.
 * @param {string} props.texto - Descrição exibida.
 */
function ItemLegenda({ situacao, texto }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className={`inline-block h-4 w-4 rounded ${ESTILO_POR_SITUACAO[situacao].celula}`}
      />
      <span>{texto}</span>
    </span>
  );
}

export default function HorizonteSaldos() {
  const [considerarMetas, setConsiderarMetas] = useState(false);
  const [considerarInvestimentos, setConsiderarInvestimentos] = useState(false);
  const [limiteAtencao, setLimiteAtencao] = useState('1000');
  const [diaSelecionado, setDiaSelecionado] = useState(null);

  const tabelaRef = useRef(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['planejamento', 'horizonte', limiteAtencao, considerarInvestimentos],
    queryFn: () =>
      buscarHorizonteSaldos({
        meses: 12,
        limiteAtencao: limiteAtencao || null,
        considerarInvestimentos,
      }),
  });

  // Detalhe do dia: só busca quando há célula selecionada, e reusa a grade do
  // calendário em vez de um endpoint dedicado.
  const { data: detalheMes, isLoading: carregandoDetalhe } = useQuery({
    queryKey: ['planejamento', 'calendario', diaSelecionado?.ano, diaSelecionado?.mes],
    queryFn: () => buscarCalendario(diaSelecionado.ano, diaSelecionado.mes),
    enabled: Boolean(diaSelecionado),
  });

  const lancamentosDoDia = useMemo(() => {
    if (!detalheMes || !diaSelecionado) return [];
    const encontrado = detalheMes.dias.find((d) => d.dia === diaSelecionado.dia);
    return encontrado?.lancamentos ?? [];
  }, [detalheMes, diaSelecionado]);

  // Índice { "ano-mes-dia": célula } para montar a grade de 31 linhas sem
  // percorrer as listas de dias a cada célula renderizada.
  const indice = useMemo(() => {
    const mapa = new Map();
    for (const mes of data?.meses ?? []) {
      for (const dia of mes.dias) {
        mapa.set(`${mes.ano}-${mes.mes}-${dia.dia}`, dia);
      }
    }
    return mapa;
  }, [data]);

  const campoSaldo = considerarMetas ? 'saldo_com_metas' : 'saldo';
  const campoSituacao = considerarMetas ? 'situacao_com_metas' : 'situacao';
  const primeiroNegativo = considerarMetas
    ? data?.primeiro_dia_negativo_com_metas
    : data?.primeiro_dia_negativo;

  if (isLoading) {
    return (
      <div role="status" className="flex flex-col items-center gap-3 py-16">
        <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">Projetando seus saldos...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <Alert variant="error" icon={AlertCircle}>
        <span className="font-medium">Não foi possível calcular a projeção de saldos.</span>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Horizonte de Saldos
        </h1>
        {/* `aria-live` porque o número muda por ação do usuário nos filtros, sem
            que nada receba foco: sem isso a troca passaria despercebida a quem
            navega por leitor de tela. */}
        <p className="mt-1 text-sm text-muted-foreground" aria-live="polite">
          Saldo acumulado projetado dia a dia, a partir de {formatarMoeda(data.saldo_inicial)} em caixa hoje
          {Number(data.valor_investido) > 0 && !data.investimentos_considerados
            ? `, já sem os ${formatarMoeda(data.valor_investido)} aplicados na carteira`
            : ''}
          .
        </p>
      </header>

      {/* O achado mais importante da tela vem antes da grade: quem abre isto
          quer saber se e quando o saldo estoura, não percorrer 370 células. */}
      {primeiroNegativo ? (
        <Alert variant="warning" icon={AlertTriangle}>
          <span className="font-medium leading-relaxed">
            Seu saldo fica negativo em <strong>{dataPorExtenso(primeiroNegativo)}</strong>
            {considerarMetas && ' considerando os aportes necessários às suas metas'}.
          </span>
        </Alert>
      ) : (
        <Alert variant="success" icon={CalendarClock}>
          <span className="font-medium leading-relaxed">
            Nenhum dia negativo nos próximos 12 meses
            {considerarMetas && ', mesmo com os aportes necessários às suas metas'}.
          </span>
        </Alert>
      )}

      {Number(data.atrasados.despesas) > 0 && (
        <Alert variant="info" icon={AlertCircle}>
          <span className="font-medium leading-relaxed">
            A projeção já desconta {formatarMoeda(data.atrasados.despesas)} em contas
            vencidas e ainda não pagas — elas entram no saldo de abertura.
          </span>
        </Alert>
      )}

      {/* Filtros numa única linha acima da grade. */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1.5">
          <label
            htmlFor="limite-atencao"
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Limite de atenção
          </label>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">R$</span>
            <input
              id="limite-atencao"
              type="number"
              inputMode="decimal"
              min="0"
              step="100"
              value={limiteAtencao}
              onChange={(e) => setLimiteAtencao(e.target.value)}
              className="h-9 w-32 rounded-xl border border-border bg-card px-3 text-sm text-foreground"
              aria-describedby="ajuda-limite-atencao"
            />
          </div>
          <p id="ajuda-limite-atencao" className="text-xs text-muted-foreground">
            Dias com saldo abaixo deste valor são sinalizados.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant={considerarMetas ? 'default' : 'outline'}
            onClick={() => setConsiderarMetas((v) => !v)}
            aria-pressed={considerarMetas}
            className="flex h-9 items-center gap-2 rounded-xl px-4 text-xs"
          >
            <Target className="h-4 w-4" aria-hidden="true" />
            Considerar aportes das metas
          </Button>

          {/* Só aparece para quem tem carteira: um botão que soma zero é ruído. */}
          {Number(data.valor_investido) > 0 && (
            <Button
              type="button"
              variant={considerarInvestimentos ? 'default' : 'outline'}
              onClick={() => setConsiderarInvestimentos((v) => !v)}
              aria-pressed={considerarInvestimentos}
              aria-describedby="ajuda-considerar-investimentos"
              className="flex h-9 items-center gap-2 rounded-xl px-4 text-xs"
            >
              <Wallet className="h-4 w-4" aria-hidden="true" />
              Considerar valor investido
            </Button>
          )}
        </div>
      </div>

      {Number(data.valor_investido) > 0 && (
        <p id="ajuda-considerar-investimentos" className="sr-only">
          Soma {formatarMoeda(data.valor_investido)}, o custo de aquisição da sua
          carteira, ao saldo de abertura da projeção. Por padrão esse valor fica de
          fora, porque dinheiro aplicado não está disponível para pagar contas.
        </p>
      )}

      <Card className="overflow-hidden rounded-2xl border-border/40">
        <CardContent className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <ItemLegenda situacao="confortavel" texto="acima do limite de atenção" />
            <ItemLegenda situacao="atencao" texto="abaixo do limite de atenção" />
            <ItemLegenda situacao="negativo" texto="negativo" />
            <span>— clique numa célula para ver os lançamentos do dia</span>
          </div>

          {/* Grade larga: rola dentro do próprio contêiner, para que a página
              nunca role horizontalmente. */}
          <div ref={tabelaRef} className="overflow-x-auto">
            <table className="w-full min-w-[64rem] border-separate border-spacing-1 text-xs">
              <caption className="sr-only">
                Saldo acumulado projetado por dia, de {dataPorExtenso(data.inicio)} a{' '}
                {dataPorExtenso(data.fim)}
                {considerarMetas
                  ? ', descontando os aportes necessários às metas'
                  : ', considerando apenas os lançamentos registrados'}
                {Number(data.valor_investido) > 0 && !data.investimentos_considerados
                  ? ', e sem o valor aplicado na carteira de investimentos'
                  : ''}
              </caption>
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="sticky left-0 z-10 bg-card px-2 py-2 text-left font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    Dia
                  </th>
                  {data.meses.map((mes) => (
                    <th
                      key={`${mes.ano}-${mes.mes}`}
                      scope="col"
                      className="px-2 py-2 text-center font-semibold uppercase tracking-wide text-muted-foreground"
                    >
                      {mes.rotulo}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {DIAS_DO_MES.map((numeroDia) => (
                  <tr key={numeroDia}>
                    <th
                      scope="row"
                      className="sticky left-0 z-10 bg-card px-2 py-1 text-left font-medium tabular-nums text-muted-foreground"
                    >
                      {numeroDia}
                    </th>

                    {data.meses.map((mes) => {
                      const celula = indice.get(`${mes.ano}-${mes.mes}-${numeroDia}`);

                      // Dia inexistente no mês, ou anterior a hoje no primeiro
                      // mês: fica vazio, sem virar zero — zero significaria saldo
                      // nulo, e não ausência de projeção.
                      if (!celula) {
                        return (
                          <td
                            key={`${mes.ano}-${mes.mes}-${numeroDia}`}
                            className="px-1 py-1"
                          />
                        );
                      }

                      const estilo = ESTILO_POR_SITUACAO[celula[campoSituacao]];
                      return (
                        <td key={`${mes.ano}-${mes.mes}-${numeroDia}`} className="px-1 py-1">
                          <button
                            type="button"
                            onClick={() =>
                              setDiaSelecionado({
                                ano: mes.ano,
                                mes: mes.mes,
                                dia: celula.dia,
                                data: celula.data,
                                saldo: celula[campoSaldo],
                              })
                            }
                            className={`w-full rounded-md px-2 py-1 text-center tabular-nums transition-colors hover:brightness-95 ${estilo.celula}`}
                          >
                            {formatarMoedaCompacta(celula[campoSaldo])}
                            {/* Terceiro sinal, para leitor de tela: a cor e a
                                borda não são percebidas por quem ouve a tabela. */}
                            <span className="sr-only">, {estilo.rotulo}</span>
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Modal
        isOpen={Boolean(diaSelecionado)}
        onClose={() => setDiaSelecionado(null)}
        title={diaSelecionado ? dataPorExtenso(diaSelecionado.data) : ''}
        description={
          diaSelecionado
            ? `Saldo projetado: ${formatarMoeda(diaSelecionado.saldo)}`
            : undefined
        }
        size="md"
      >
        {carregandoDetalhe ? (
          <div role="status" className="flex items-center gap-2 py-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
            <span className="text-sm text-muted-foreground">Carregando lançamentos...</span>
          </div>
        ) : lancamentosDoDia.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            Nenhum lançamento previsto para este dia. O saldo exibido é o acumulado
            dos dias anteriores.
          </p>
        ) : (
          <ul className="divide-y divide-border/40">
            {lancamentosDoDia.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-4 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">{item.descricao}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.categoria || 'Sem categoria'}
                    {item.cartao && ` · ${item.cartao}`}
                    {item.recorrente && ' · recorrente'}
                    {item.realizado ? ' · liquidado' : ' · pendente'}
                  </p>
                </div>
                <span
                  className={`shrink-0 text-sm font-semibold tabular-nums ${
                    item.tipo === 'R'
                      ? 'text-emerald-800 dark:text-emerald-300'
                      : 'text-red-700 dark:text-red-300'
                  }`}
                >
                  {item.tipo === 'R' ? '+' : '−'} {formatarMoeda(item.valor)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </div>
  );
}
