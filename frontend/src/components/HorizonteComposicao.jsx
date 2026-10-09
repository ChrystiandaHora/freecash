/**
 * Composição do saldo — a memória de cálculo do Horizonte de Saldos.
 *
 * A grade responde *quanto* vai haver em cada dia; esta aba responde *por quê*. Ela
 * existe porque o número de abertura engana fácil: é o caixa realizado **até ontem**,
 * e o que foi pago ou recebido hoje entra como movimento do dia, não na abertura.
 * Sem a decomposição, quem paga uma conta hoje vê o saldo de abertura parado e conclui
 * que o lançamento não foi considerado.
 *
 * Abaixo do caixa de hoje vem a linha do tempo (`HorizonteLinhaDoTempo`), do primeiro
 * lançamento até 12 meses à frente, e por último o detalhe do mês escolhido nela.
 *
 * Tudo vem pronto do servidor, da mesma lista de lançamentos que monta a curva — a aba
 * não refaz a regra de qual lançamento entra em qual dia.
 */
import { useState } from 'react';
import { Sparkles } from 'lucide-react';

import HorizonteLinhaDoTempo from './HorizonteLinhaDoTempo';
import { ValorComSinal } from './HorizonteValores';
import { Card, CardContent } from './ui/Card';
import { formatarMoeda } from '../lib/moeda';

/**
 * Formata uma data ISO como dia/mês.
 *
 * @param {string} iso - Data no formato AAAA-MM-DD.
 * @returns {string} Data curta, por exemplo "09/10".
 */
function diaMes(iso) {
  const [, mes, dia] = iso.split('-');
  return `${dia}/${mes}`;
}

/**
 * Nome do mês por extenso, em português.
 *
 * @param {{ano: number, mes: number}} mes - Mês da projeção.
 * @returns {string} Por exemplo "outubro de 2026".
 */
function nomeDoMes({ ano, mes }) {
  return new Date(ano, mes - 1, 1).toLocaleDateString('pt-BR', {
    month: 'long',
    year: 'numeric',
  });
}

/**
 * Explica em que data o lançamento move o saldo, quando ela difere da prevista.
 *
 * É a linha que esclarece o caso mais confuso: conta prevista num mês e liquidada
 * em outro move o saldo na data da liquidação.
 */
function linhaDeData(item) {
  if (!item.realizado) return `previsto para ${diaMes(item.data)}`;
  const verbo = item.tipo === 'R' ? 'recebido' : 'pago';
  if (item.data !== item.data_prevista) {
    return `${verbo} em ${diaMes(item.data)} (previsto para ${diaMes(item.data_prevista)})`;
  }
  return `${verbo} em ${diaMes(item.data)}`;
}

/**
 * Lista dos maiores lançamentos de um tipo no mês, com o resumo do restante.
 *
 * @param {string} props.titulo - Cabeçalho da lista.
 * @param {'R'|'D'} props.tipo - Receita ou despesa.
 * @param {Object} props.grupo - `composicao.receitas` ou `composicao.despesas`.
 * @param {string} props.total - Total do tipo no mês.
 */
function ListaDoTipo({ titulo, tipo, grupo, total }) {
  const sinal = tipo === 'R' ? '+' : '−';
  const idTitulo = `composicao-${tipo}`;

  return (
    <section aria-labelledby={idTitulo} className="min-w-0 space-y-2">
      <h4 id={idTitulo} className="flex items-baseline justify-between gap-2 text-sm font-semibold text-foreground">
        <span>{titulo}</span>
        <ValorComSinal valor={total} sinal={sinal} />
      </h4>

      {grupo.maiores.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum lançamento neste mês.</p>
      ) : (
        <ul className="divide-y divide-border/40">
          {grupo.maiores.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-4 py-2">
              <div className="min-w-0">
                <p className="break-words text-sm font-medium text-foreground">{item.descricao}</p>
                <p className="text-xs text-muted-foreground">
                  {linhaDeData({ ...item, tipo })}
                  {item.categoria && ` · ${item.categoria}`}
                </p>
                {item.evento && (
                  <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-primary">
                    <Sparkles className="h-3 w-3" aria-hidden="true" />
                    Evento: {item.evento}
                  </p>
                )}
              </div>
              <span className="shrink-0 text-sm font-semibold">
                <ValorComSinal valor={item.valor} sinal={sinal} />
              </span>
            </li>
          ))}
          {grupo.outros_qtd > 0 && (
            <li className="flex items-start justify-between gap-4 py-2 text-sm text-muted-foreground">
              <span>
                Outros {grupo.outros_qtd} {grupo.outros_qtd === 1 ? 'lançamento' : 'lançamentos'}
              </span>
              <span className="shrink-0 tabular-nums">
                {sinal} {formatarMoeda(grupo.outros_total)}
              </span>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

/**
 * Aba de composição do saldo.
 *
 * @param {Object} props.data - Resposta de `/api/planejamento/horizonte-saldos/`.
 * @param {boolean} props.considerarMetas - Se o cenário de metas está ligado.
 */
export default function HorizonteComposicao({ data, considerarMetas }) {
  const [mesSelecionado, setMesSelecionado] = useState(0);

  const sufixo = considerarMetas ? '_com_metas' : '';
  const investidoFora = Number(data.valor_investido) > 0 && !data.investimentos_considerados;
  const ontem = new Date(`${data.inicio}T00:00:00`);
  ontem.setDate(ontem.getDate() - 1);

  const mes = data.meses[mesSelecionado] ?? data.meses[0];
  const abertura = Number(mes[`saldo_abertura${sufixo}`]);
  const fechamento = Number(mes[`saldo_final${sufixo}`]);

  return (
    <div className="space-y-6">
      <Card className="rounded-2xl border-border/40">
        <CardContent className="space-y-3 p-4">
          <h3 className="text-base font-semibold text-foreground">De onde vem o caixa de hoje</h3>
          <table className="w-full text-sm">
            <caption className="sr-only">Composição do caixa de abertura da projeção</caption>
            <tbody className="divide-y divide-border/40">
              <tr>
                <th scope="row" className="py-2 pr-4 text-left font-normal text-foreground">
                  Saldo realizado até{' '}
                  {ontem.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })}
                </th>
                <td className="py-2 text-right tabular-nums text-foreground">
                  {formatarMoeda(data.caixa_realizado)}
                </td>
              </tr>
              {Number(data.atrasados.receitas) > 0 && (
                <tr>
                  <th scope="row" className="py-2 pr-4 text-left font-normal text-foreground">
                    Receitas vencidas ainda não recebidas
                  </th>
                  <td className="py-2 text-right">
                    <ValorComSinal valor={data.atrasados.receitas} sinal="+" />
                  </td>
                </tr>
              )}
              {Number(data.atrasados.despesas) > 0 && (
                <tr>
                  <th scope="row" className="py-2 pr-4 text-left font-normal text-foreground">
                    Contas vencidas ainda não pagas
                  </th>
                  <td className="py-2 text-right">
                    <ValorComSinal valor={data.atrasados.despesas} sinal="−" />
                  </td>
                </tr>
              )}
              {investidoFora && (
                <tr>
                  <th scope="row" className="py-2 pr-4 text-left font-normal text-foreground">
                    Valor aplicado na carteira (fica fora do saldo)
                  </th>
                  <td className="py-2 text-right">
                    <ValorComSinal valor={data.valor_investido} sinal="−" />
                  </td>
                </tr>
              )}
              <tr>
                <th scope="row" className="py-2 pr-4 text-left font-semibold text-foreground">
                  = Caixa de abertura hoje
                </th>
                <td className="py-2 text-right font-semibold tabular-nums text-foreground">
                  {formatarMoeda(data.saldo_inicial)}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="text-xs text-muted-foreground">
            O que foi pago ou recebido hoje não muda este número: entra como movimento do
            dia de hoje, no primeiro mês da tabela abaixo.
          </p>
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-border/40">
        <CardContent className="space-y-3 p-4">
          <h3 className="text-base font-semibold text-foreground">
            Do primeiro lançamento até os próximos 12 meses
          </h3>
          <p className="text-xs text-muted-foreground">
            Clique num mês projetado na tabela para ver os lançamentos que explicam a variação.
          </p>
          <HorizonteLinhaDoTempo
            data={data}
            considerarMetas={considerarMetas}
            mesSelecionado={mesSelecionado}
            onSelecionarMes={setMesSelecionado}
          />
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-border/40">
        <CardContent className="space-y-4 p-4">
          <section id="composicao-detalhe-mes" aria-labelledby="composicao-titulo-mes" className="space-y-4">
            <div>
              <h3 id="composicao-titulo-mes" className="text-base font-semibold text-foreground">
                Por que o saldo mudou em {nomeDoMes(mes)}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {formatarMoeda(abertura)} na abertura{' '}
                <ValorComSinal valor={mes.total_receitas} sinal="+" /> de entradas{' '}
                <ValorComSinal valor={mes.total_despesas} sinal="−" /> de saídas
                {considerarMetas && Number(mes.aporte_metas) > 0 && (
                  <>
                    {' '}<ValorComSinal valor={mes.aporte_metas} sinal="−" /> de aporte às metas
                  </>
                )}
                {' '}= <strong className="text-foreground">{formatarMoeda(fechamento)}</strong> no fechamento.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <ListaDoTipo
                titulo="Entradas"
                tipo="R"
                grupo={mes.composicao.receitas}
                total={mes.total_receitas}
              />
              <ListaDoTipo
                titulo="Saídas"
                tipo="D"
                grupo={mes.composicao.despesas}
                total={mes.total_despesas}
              />
            </div>
          </section>
        </CardContent>
      </Card>
    </div>
  );
}
