/**
 * Painel de métricas de uso da plataforma.
 *
 * Mostra indicadores de contas e a curva de cadastros. Não mostra — e não deve
 * passar a mostrar — nenhum dado financeiro de usuário: administrar a plataforma
 * não exige ver as finanças de ninguém, e o servidor sequer devolve esses campos.
 *
 * Escolhas de visualização, seguindo a ordem "forma antes da cor":
 * - Os indicadores são **números**, não gráficos. Uma contagem única não ganha nada
 *   ao virar barra; o número lido direto é mais rápido e mais preciso.
 * - Os cadastros ao longo do tempo são **uma série só**, e por isso dispensam
 *   legenda: o título do gráfico já a nomeia. Uma legenda de um item é ruído.
 * - A cor da série é o `#007acc` da marca, o mesmo usado nos gráficos do resto do
 *   aplicativo. Ele reprova como texto corrido (3,89:1) mas passa como elemento
 *   não-textual, que exige 3:1 — e uma linha de gráfico é elemento não-textual.
 * - Há uma tabela alternativa dos mesmos dados, para que a informação não dependa
 *   de leitura gráfica.
 *
 * @module AdminMetricas
 * @component
 * @returns {React.JSX.Element}
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApexCharts from 'react-apexcharts';
import { AlertCircle, Loader2, ShieldCheck, UserCheck, UserPlus, Users, UserX } from 'lucide-react';

import { Alert } from '../../components/ui/Alert';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { buscarMetricas } from '../../services/admin';

const COR_SERIE = '#007acc';
const JANELAS = [
  { valor: 7, rotulo: '7 dias' },
  { valor: 30, rotulo: '30 dias' },
  { valor: 90, rotulo: '90 dias' },
];

/**
 * Indicador numérico único.
 *
 * @param {Object} props - Propriedades do componente.
 * @param {React.ComponentType} props.icon - Ícone ilustrativo.
 * @param {string} props.rotulo - Nome do indicador.
 * @param {string|number} props.valor - Valor exibido.
 * @param {string} [props.apoio] - Linha de contexto abaixo do valor.
 * @returns {React.JSX.Element}
 */
function Indicador({ icon: Icon, rotulo, valor, apoio }) {
  return (
    <Card className="rounded-2xl border-border/40">
      <CardContent className="flex items-start gap-3 p-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <Icon className="h-4.5 w-4.5 text-primary" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {rotulo}
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">{valor}</p>
          {apoio && <p className="mt-0.5 text-xs text-muted-foreground">{apoio}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminMetricas() {
  const [dias, setDias] = useState(30);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin', 'metricas', dias],
    queryFn: () => buscarMetricas(dias),
  });

  // Memoizado porque `?? []` produziria um array novo a cada render, invalidando
  // o useMemo das opções do gráfico e remontando o Apex sem necessidade.
  const serie = useMemo(() => data?.cadastros_por_dia ?? [], [data]);

  const opcoesGrafico = useMemo(
    () => ({
      chart: {
        type: 'area',
        height: 280,
        toolbar: { show: false },
        fontFamily: 'inherit',
        // O gráfico é decoração de um dado que também existe em tabela: não
        // precisa de animação, e removê-la respeita quem pediu menos movimento.
        animations: { enabled: false },
      },
      colors: [COR_SERIE],
      // Traço de 2px: fino o suficiente para não dominar, grosso o suficiente
      // para sobreviver à escala de cinza e ao zoom.
      stroke: { curve: 'smooth', width: 2 },
      fill: {
        type: 'gradient',
        gradient: { opacityFrom: 0.25, opacityTo: 0.02, shadeIntensity: 1 },
      },
      dataLabels: { enabled: false },
      grid: { borderColor: 'rgba(136,136,136,0.2)', strokeDashArray: 4 },
      xaxis: {
        categories: serie.map((item) => item.data),
        labels: {
          style: { colors: '#888888', fontSize: '12px' },
          formatter: (valor) =>
            valor ? new Date(`${valor}T00:00:00`).toLocaleDateString('pt-BR', {
              day: '2-digit',
              month: '2-digit',
            }) : '',
        },
        axisBorder: { show: false },
        axisTicks: { show: false },
        tooltip: { enabled: false },
      },
      yaxis: {
        labels: {
          style: { colors: '#888888', fontSize: '12px' },
          formatter: (valor) => Math.round(valor),
        },
        min: 0,
        // Contagem de pessoas é inteira: um eixo com 0,5 conta não significa nada.
        forceNiceScale: true,
      },
      tooltip: {
        theme: 'dark',
        x: {
          formatter: (_, { dataPointIndex }) => {
            const bruto = serie[dataPointIndex]?.data;
            return bruto
              ? new Date(`${bruto}T00:00:00`).toLocaleDateString('pt-BR', {
                  day: '2-digit',
                  month: 'long',
                  year: 'numeric',
                })
              : '';
          },
        },
        y: {
          formatter: (valor) =>
            `${valor} ${valor === 1 ? 'cadastro' : 'cadastros'}`,
          title: { formatter: () => '' },
        },
      },
      // Uma série só: legenda de um item é ruído, o título do cartão já a nomeia.
      legend: { show: false },
    }),
    [serie]
  );

  if (isLoading) {
    return (
      <div role="status" className="flex flex-col items-center gap-3 py-16">
        <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">Carregando métricas...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <Alert variant="error" icon={AlertCircle}>
        <span className="font-medium">
          Não foi possível carregar as métricas da plataforma.
        </span>
      </Alert>
    );
  }

  const c = data.contas;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Métricas da plataforma
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Indicadores de contas e adoção. Nenhum dado financeiro de usuário é exibido aqui.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Indicador
          icon={Users}
          rotulo="Contas totais"
          valor={c.total}
          apoio={`${c.ativas} ativas · ${c.suspensas} suspensas`}
        />
        <Indicador
          icon={ShieldCheck}
          rotulo="E-mail confirmado"
          valor={`${data.percentual_verificado}%`}
          apoio={`${c.verificadas} de ${c.total} contas`}
        />
        <Indicador
          icon={UserPlus}
          rotulo="Novas contas"
          valor={c.novas_30d}
          apoio={`${c.novas_7d} nos últimos 7 dias`}
        />
        <Indicador
          icon={UserCheck}
          rotulo="Acessaram em 30 dias"
          valor={c.ativos_30d}
          apoio={`${c.ativos_7d} nos últimos 7 dias`}
        />
        <Indicador
          icon={UserX}
          rotulo="Nunca acessaram"
          valor={c.nunca_acessaram}
          apoio="Cadastraram e não voltaram"
        />
        <Indicador
          icon={ShieldCheck}
          rotulo="Administradores"
          valor={c.administradores}
          apoio="Contas com acesso a este painel"
        />
      </div>

      <Card className="rounded-2xl border-border/40">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base font-semibold">Cadastros por dia</CardTitle>

          {/* Filtro numa única linha acima do gráfico. */}
          <div role="group" aria-label="Período do gráfico" className="flex gap-1">
            {JANELAS.map(({ valor, rotulo }) => (
              <button
                key={valor}
                type="button"
                onClick={() => setDias(valor)}
                aria-pressed={dias === valor}
                className={
                  dias === valor
                    ? 'rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground'
                    : 'rounded-lg px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted'
                }
              >
                {rotulo}
              </button>
            ))}
          </div>
        </CardHeader>

        <CardContent>
          <ApexCharts
            options={opcoesGrafico}
            series={[{ name: 'Cadastros', data: serie.map((item) => item.total) }]}
            type="area"
            height={280}
          />

          {/* Os mesmos dados em tabela: a informação não pode depender de leitura
              gráfica. Fechada por padrão para não competir com o gráfico. */}
          <details className="mt-4">
            <summary className="cursor-pointer text-xs font-semibold text-primary">
              Ver os dados em tabela
            </summary>
            <div className="mt-3 max-h-64 overflow-auto">
              <table className="w-full text-left text-xs">
                <caption className="sr-only">
                  Cadastros por dia nos últimos {dias} dias
                </caption>
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b border-border">
                    <th scope="col" className="py-2 pr-4 font-semibold text-muted-foreground">
                      Data
                    </th>
                    <th scope="col" className="py-2 font-semibold text-muted-foreground">
                      Cadastros
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {serie.map((item) => (
                    <tr key={item.data} className="border-b border-border/40">
                      <td className="py-1.5 pr-4 text-foreground">
                        {new Date(`${item.data}T00:00:00`).toLocaleDateString('pt-BR')}
                      </td>
                      <td className="py-1.5 tabular-nums text-foreground">{item.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </CardContent>
      </Card>
    </div>
  );
}
