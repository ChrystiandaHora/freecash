/**
 * Tela de Consulta e Detalhe de Cartões de Crédito (Meus Cartões).
 * 
 * Agrega dados de limites e faturas atuais de múltiplos cartões cadastrados.
 * Exibe cartões em formato visual de cartão físico, barras de progresso de utilização de limite,
 * resumo de provisões e accordion dinâmico contendo o extrato de compras recentes de cada cartão.
 *
 * @component
 * @returns {React.JSX.Element} Grid com cartões e resumos consolidados de faturas.
 */
import { useQuery } from '@tanstack/react-query';
import {
  CreditCard, Wallet, RefreshCw,
  ShoppingCart, Utensils, Car, Fuel
} from 'lucide-react';

import Chart from 'react-apexcharts';
import { fetchCartoes } from '../services/financeiro';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Accordion, AccordionItem } from '../components/ui/Accordion';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const CARD_BGS = [
  'bg-[#007acc] text-white',
  'bg-[#161b22] text-white border border-border/40',
  'bg-[#1f2937] text-white',
  'bg-[#0f172a] text-white',
  'bg-[#090d16] text-white',
]

const CATEGORY_ICONS = {
  'alimentação': Utensils,
  'transporte': Car,
  'combustível': Fuel,
  'compras': ShoppingCart,
  'default': ShoppingCart,
}

const getCategoryIcon = (cat = '') => {
  const key = cat.toLowerCase()
  return CATEGORY_ICONS[key] || CATEGORY_ICONS.default
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

const CardSkeleton = () => (
  <div className="rounded-2xl border border-border/60 overflow-hidden">
    <div className="h-48 animate-pulse bg-muted" />
    <div className="p-5 space-y-3">
      <div className="h-3 animate-pulse rounded bg-muted w-1/3" />
      <div className="h-2 animate-pulse rounded bg-muted w-full" />
      <div className="h-8 animate-pulse rounded bg-muted w-1/2" />
    </div>
  </div>
)

// ─── Componente de Cartão Visual ──────────────────────────────────────────────

const CreditCardVisual = ({ cartao, bgClass }) => {
  const limite = Number(cartao.limite ?? 0)
  const usado = Number(cartao.fatura_atual ?? 0)
  const disponivel = Math.max(limite - usado, 0)
  const pct = limite > 0 ? (usado / limite) * 100 : 0

  const compras = cartao.compras_recentes ?? []

  // Configurações do gráfico de velocímetro (Gauge)
  const chartGaugeOptions = {
    chart: {
      type: 'radialBar',
      sparkline: { enabled: true },
      animations: { enabled: false }
    },
    colors: [
      pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981'
    ],
    plotOptions: {
      radialBar: {
        startAngle: -95,
        endAngle: 95,
        track: {
          background: document.documentElement.classList.contains('dark') ? 'rgba(255, 255, 255, 0.05)' : '#f1f5f9',
          strokeWidth: '85%',
        },
        dataLabels: {
          name: { show: false },
          value: {
            offsetY: -3,
            fontSize: '13px',
            fontWeight: '800',
            color: 'inherit',
            formatter: (val) => `${val.toFixed(0)}%`
          }
        }
      }
    },
    fill: { type: 'solid' },
    stroke: { lineCap: 'round' },
    theme: {
      mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    }
  };

  return (
    <div className="rounded-2xl border border-border/60 overflow-hidden bg-card transition-all duration-300 hover:shadow-xl hover:-translate-y-0.5">
      {/* Visual do Cartão */}
      <div className={`relative h-48 ${bgClass} p-6 flex flex-col justify-between overflow-hidden`}>
        {/* Padrão decorativo sutil */}
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/5" />
        <div className="absolute -right-4 top-12 h-20 w-20 rounded-full bg-white/5" />

        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium opacity-60 uppercase tracking-wider">Banco</p>
            <p className="text-lg font-bold">{cartao.banco || cartao.nome || 'Cartão'}</p>
          </div>
          <CreditCard className="h-8 w-8 opacity-70" />
        </div>

        <div>
          <p className="font-mono text-lg font-semibold opacity-80 tracking-widest">
            •••• •••• •••• {cartao.final || '0000'}
          </p>
          <div className="flex items-center justify-between mt-2">
            <div>
              <p className="text-xs opacity-60">Titular</p>
              <p className="text-sm font-semibold">{cartao.titular || 'Usuário'}</p>
            </div>
            <div className="text-right">
              <p className="text-xs opacity-60">Validade</p>
              <p className="text-sm font-semibold">{cartao.validade || '12/29'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Informações do Limite */}
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-grow">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Fatura Atual</p>
            <p className="text-xl font-extrabold text-foreground">{formatCurrency(usado)}</p>
            
            <div className="mt-2 space-y-0.5 text-xs text-muted-foreground">
              <p>Limite: <span className="font-bold text-foreground/80">{formatCurrency(limite)}</span></p>
              <p>Disponível: <span className="font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(disponivel)}</span></p>
            </div>
          </div>

          <div className="w-24 h-20 overflow-hidden flex items-center justify-center shrink-0" style={{ color: pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981' }}>
            <Chart
              options={chartGaugeOptions}
              series={[pct]}
              type="radialBar"
              height={140}
              width={120}
            />
          </div>
        </div>

        {/* Fatura / Compras Recentes */}
        <Accordion>
          <AccordionItem title={`Fatura atual (${compras.length} transações)`}>
            {compras.length === 0 ? (
              <p className="py-2 text-xs text-muted-foreground">Nenhuma compra no período.</p>
            ) : (
              <div className="space-y-2 py-1">
                {compras.slice(0, 8).map((compra, idx) => {
                  const Icon = getCategoryIcon(compra.categoria)
                  return (
                    <div key={compra.id ?? idx} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted">
                          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground leading-tight">{compra.descricao}</p>
                          <p className="text-muted-foreground">{compra.data}</p>
                        </div>
                      </div>
                      <span className="font-semibold text-foreground">{formatCurrency(compra.valor)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </AccordionItem>
        </Accordion>
      </div>
    </div>
  )
}

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function MeusCartoes() {
  const { data: cartoes = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['cartoes'],
    queryFn: () => fetchCartoes(),
  })

  const totalLimite = cartoes.reduce((acc, c) => acc + Number(c.limite ?? 0), 0)
  const totalUsado = cartoes.reduce((acc, c) => acc + Number(c.fatura_atual ?? 0), 0)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Meus Cartões
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Visão consolidada de limites e faturas
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-1.5 h-4 w-4" />
          Atualizar
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Limite Total
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{formatCurrency(totalLimite)}</p>
            <p className="text-xs text-muted-foreground mt-1">{cartoes.length} cartão(ões)</p>
          </CardContent>
        </Card>

        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Total em Faturas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{formatCurrency(totalUsado)}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {totalLimite > 0 ? ((totalUsado / totalLimite) * 100).toFixed(1) : 0}% do limite total
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Disponível Total
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(totalLimite - totalUsado)}</p>
            <p className="text-xs text-muted-foreground mt-1">Crédito restante</p>
          </CardContent>
        </Card>
      </div>

      {/* Error state */}
      {isError && (
        <Alert variant="error">
          Não foi possível carregar os cartões. Verifique a conexão com a API.
        </Alert>
      )}

      {/* Grid de Cartões */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading
          ? Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} />)
          : cartoes.length === 0
          ? (
            <div className="col-span-3 rounded-xl border border-dashed border-border/60 p-16 text-center">
              <Wallet className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="text-muted-foreground">Nenhum cartão cadastrado ainda.</p>
            </div>
          )
          : cartoes.map((cartao, idx) => (
            <CreditCardVisual
              key={cartao.id ?? idx}
              cartao={cartao}
              bgClass={CARD_BGS[idx % CARD_BGS.length]}
            />
          ))
        }
      </div>
    </div>
  )
}
