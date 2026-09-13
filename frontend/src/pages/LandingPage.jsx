/**
 * Landing Page de Alta Conversão do FreeCash.
 *
 * Página pública, responsiva (mobile-first), otimizada para SEO e conversão,
 * compatível com Dark/Light mode através dos tokens semânticos do Tailwind CSS v4.
 *
 * Seções:
 * 1. Navbar Flutuante (Brand, links âncora, ThemeToggle, Login/CTA, Drawer Mobile)
 * 2. Hero Section (Headline, badges de confiança, CTA duplo, mockup dinâmico do Dashboard)
 * 3. Problema vs. Solução (Comparativo persuasivo: planilhas vs. FreeCash)
 * 4. Recursos e Benefícios (6 cards com ícones minimalistas e micro-interações)
 * 5. Showcase de Telas (Tabs interativas com visualização de screenshots reais do sistema)
 * 6. Prova Social & Números (Métricas de impacto e depoimentos de usuários)
 * 7. FAQ Interativo (Acordeão acessível com as dúvidas frequentes)
 * 8. CTA Final & Rodapé (Chamada de fechamento, links rápidos e copyright)
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Wallet,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Kanban,
  Calculator,
  CreditCard,
  FileSpreadsheet,
  ChevronDown,
  Sparkles,
  Lock,
  Star,
  Menu,
  X,
  Zap,
} from 'lucide-react';
import { ThemeToggle } from '../components/nav/ThemeToggle';
import { cn } from '../lib/utils';

// Features principais do sistema com os grandes diferenciais de mercado
const FEATURES = [
  {
    icon: Kanban,
    title: 'Pipeline Kanban de Contas',
    description:
      'Controle visual de contas a pagar inexistente em outros apps. Arraste despesas entre colunas e liquide com um clique, sem perder datas de vencimento ou pagar juros.',
    badge: 'Inovação Visual',
  },
  {
    icon: Sparkles,
    title: 'Calculadora de Aporte Mágico',
    description:
      'Digite quanto deseja investir hoje e o algoritmo calcula em tempo real as cotas exatas a comprar para reequilibrar sua carteira, sem precisar vender ativos nem pagar IR.',
    badge: 'Exclusivo Investidores',
  },
  {
    icon: Calculator,
    title: 'Simulador Sandbox (12 Meses)',
    description:
      'Previsibilidade real antes de gastar. Simule compras parceladas em ambiente isolado e detecte o Ponto de Virada com heatmap de fluxo de caixa futuro.',
    badge: 'Inteligência Preditiva',
  },
  {
    icon: TrendingUp,
    title: 'Investimentos ANBIMA 3 Níveis',
    description:
      'Carteira multi-ativos profissional (Renda Fixa, Ações, FIIs, Internacional e Cripto) com cotações automáticas e rentabilidade real ponderada.',
    badge: 'Padrão Institucional',
  },
  {
    icon: CreditCard,
    title: 'Gestão Executiva de Cartões',
    description:
      'Gauges circulares de utilização de limites, acompanhamento de faturas abertas/fechadas e previsão das parcelas nos próximos meses em um painel unificado.',
    badge: 'Controle Diário',
  },
  {
    icon: FileSpreadsheet,
    title: 'Importação & Backups Criptografados',
    description:
      'Importe extratos bancários e faturas em PDF com conciliação ágil. Seus dados isolados sob seu controle, com zero rastreamento e sem anúncios.',
    badge: 'Privacidade Absoluta',
  },
];

// Showcase de Telas reais do FreeCash em ordem estratégica de persuasão
const SCREEN_SHOWCASES = [
  {
    id: 'dashboard',
    label: 'Dashboard Financeiro',
    title: 'Visão 360° da sua Saúde Financeira',
    description:
      'Consolide receitas, despesas, saldo acumulado e distribuição de maiores gastos por categoria em tempo real, com gráfico de fluxo diário e projeções preditivas.',
    image: '/screenshots/01-dashboard.png',
    alt: 'Dashboard Financeiro do FreeCash',
    highlights: [
      'Fluxo de caixa diário em gráfico interativo',
      'Breakdown de maiores despesas por categoria',
      'Taxa de poupança calculada automaticamente',
    ],
  },
  {
    id: 'kanban',
    label: 'Pipeline Kanban',
    title: 'Controle Visual de Contas com Arraste e Baixa em 1 Clique',
    description:
      'Trate seus pagamentos como um fluxo de trabalho ágil. Arraste despesas entre colunas (Atrasadas, Vence Hoje, Pendentes) e, ao soltar em "Pagas", o pagamento é baixado automaticamente no sistema.',
    image: '/screenshots/03-pipeline-kanban.png',
    alt: 'Pipeline Kanban de Contas a Pagar do FreeCash',
    highlights: [
      'Interface drag & drop intuitiva que elimina o estresse de contas',
      'Liquidação contábil imediata ao mover para a coluna "Pagas"',
      'Totalizadores por coluna para planejamento semanal preciso',
    ],
  },
  {
    id: 'balanceamento',
    label: 'Aporte Mágico & Rebalanceamento',
    title: 'O Fim das Planilhas Complexas de Investimento',
    description:
      'Defina suas metas por classe de ativo (como 20% em cada uma). Informe quanto deseja aportar hoje e a Calculadora de Aporte Mágico calcula as compras exatas para reequilibrar seu patrimônio sem pagar Imposto de Renda desnecessário.',
    image: '/screenshots/09-balanceamento.png',
    alt: 'Calculadora de Aporte Mágico e Balanceamento de Ativos do FreeCash',
    highlights: [
      'Calculadora de aporte por déficit percentual da carteira',
      'Metas ideais por classe ANBIMA e por ativo individual',
      'Rebalanceamento contínuo sem necessidade de venda de ativos',
    ],
  },
  {
    id: 'simulador',
    label: 'Simulador Sandbox (12 Meses)',
    title: 'Previsibilidade Preditiva Antes de Passar o Cartão',
    description:
      'Apps tradicionais só mostram onde você já errou no passado. O Simulador do FreeCash projeta seu fluxo de caixa em até 12 meses em um ambiente Sandbox seguro. Descubra o "Ponto de Virada" e saiba exatamente se uma nova despesa comprometerá seu futuro.',
    image: '/screenshots/12-simulador-gastos.png',
    alt: 'Simulador de Gastos do FreeCash',
    highlights: [
      'Ambiente Sandbox: simule compras sem alterar dados reais',
      'Alerta de Ponto de Virada e heatmap diário de saldos',
      'Projeção de fluxo de caixa em até 12 meses no futuro',
    ],
  },
  {
    id: 'investimentos',
    label: 'Investimentos & Bola de Neve',
    title: 'Aceleração da Renda Passiva e Dividendos',
    description:
      'Patrimônio total consolidado, alocação por classe em gráfico donut, rentabilidade real ponderada e evolução histórica do Efeito Bola de Neve gerado pelo reinvestimento dos dividendos.',
    image: '/screenshots/07-investimentos-dashboard.png',
    alt: 'Dashboard de Investimentos do FreeCash',
    highlights: [
      'Gráfico de Efeito Bola de Neve com evolução de proventos',
      'Hierarquia ANBIMA de 3 níveis para máxima diversificação',
      'Cotações atualizadas e rentabilidade real consolidada',
    ],
  },
  {
    id: 'cartoes',
    label: 'Meus Cartões',
    title: 'Visão Executiva Centralizada de Limites e Faturas',
    description:
      'Monitore todos os seus cartões em uma única tela elegante com gauges interativos. Acompanhe limites disponíveis, datas de fechamento/vencimento e o impacto de compras parceladas sem precisar abrir 4 aplicativos bancários.',
    image: '/screenshots/06-meus-cartoes.png',
    alt: 'Gestão de Cartões de Crédito do FreeCash',
    highlights: [
      'Gauges circulares de limite disponível e comprometido',
      'Previsão de impacto de parcelas nas próximas faturas',
      'Histórico unificado de compras por cartão de crédito',
    ],
  },
];

// Depoimentos para Prova Social
const TESTIMONIALS = [
  {
    name: 'Lucas Prado',
    role: 'Engenheiro de Software & Investidor',
    content:
      'Eu gastava horas todo domingo mantendo três planilhas que sempre quebravam quando eu alterava uma fórmula. O FreeCash unificou o pagamento das contas com minha carteira de FIIs e Ações de um jeito impecável.',
    rating: 5,
    avatar: 'LP',
  },
  {
    name: 'Camila Fontes',
    role: 'Consultora de Negócios Autônoma',
    content:
      'O simulador de gastos é sensacional. Consegui ver exatamente como uma compra parcelada impactaria meu fluxo de caixa daqui a 6 meses. O Kanban de contas a pagar me salvou de pagar juros de atraso.',
    rating: 5,
    avatar: 'CF',
  },
  {
    name: 'Roberto Guimarães',
    role: 'Investidor Pessoa Física',
    content:
      'Privacidade era minha maior preocupação com apps tradicionais que vendem nossos dados para financeiras. O FreeCash ser isolado e ter classificação ANBIMA de verdade é um divisor de águas.',
    rating: 5,
    avatar: 'RG',
  },
];

// FAQ Acordeão
const FAQS = [
  {
    q: 'O FreeCash é realmente seguro e preserva minha privacidade?',
    a: 'Sim, totalmente. O FreeCash foi projetado com arquitetura focada em soberania de dados. Seus dados financeiros não são vendidos, não há anúncios e a autenticação utiliza tokens JWT com cookies HttpOnly seguros e backups com criptografia ponta a ponta.',
  },
  {
    q: 'Como funciona o acompanhamento de investimentos e cotações?',
    a: 'O sistema se integra diretamente a feeds de cotação atualizados (como Yahoo Finance) para ações, FIIs, BDRs e ETFs. Ele calcula automaticamente preço médio, lucro/prejuízo acumulado, percentual de alocação por classe ANBIMA e evolução de proventos.',
  },
  {
    q: 'Consigo importar faturas de cartão e extratos bancários?',
    a: 'Sim! O FreeCash conta com módulo dedicado de importação de arquivos bancários (incluindo extratos e faturas em PDF/OFX), permitindo conciliação em lote sem digitação manual exaustiva.',
  },
  {
    q: 'Preciso ter conhecimentos avançados de finanças ou contabilidade?',
    a: 'Não. A interface foi construída para ser limpa, intuitiva e direta. O Pipeline Kanban torna a gestão de contas a pagar tão simples quanto mover um cartão, enquanto os dashboards oferecem resumos claros sem jargões desnecessários.',
  },
  {
    q: 'A plataforma funciona bem em celulares e tablets?',
    a: 'Sim! Toda a interface foi desenhada seguindo a metodologia Mobile-First com componentes responsivos, garantindo navegação confortável em qualquer tamanho de tela.',
  },
];

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeScreenIndex, setActiveScreenIndex] = useState(0);
  const [openFaqIndex, setOpenFaqIndex] = useState(0);

  const activeScreen = SCREEN_SHOWCASES[activeScreenIndex];

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20 selection:text-primary">
      {/* ─── 1. NAVBAR FLUTUANTE ────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/85 backdrop-blur-md transition-colors">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Logo & Marca */}
          <Link
            to="/"
            className="group flex items-center gap-2.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-lg"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md shadow-primary/25 transition-transform group-hover:scale-105">
              <Wallet className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xl font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
                FreeCash
              </span>
              <span className="hidden sm:inline-block rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                PRO
              </span>
            </div>
          </Link>

          {/* Links Desktop */}
          <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-muted-foreground">
            <a href="#solucao" className="hover:text-foreground transition-colors">
              Por que FreeCash
            </a>
            <a href="#features" className="hover:text-foreground transition-colors">
              Recursos
            </a>
            <a href="#telas" className="hover:text-foreground transition-colors">
              Demonstração
            </a>
            <a href="#depoimentos" className="hover:text-foreground transition-colors">
              Depoimentos
            </a>
            <a href="#faq" className="hover:text-foreground transition-colors">
              FAQ
            </a>
          </nav>

          {/* Ações Desktop */}
          <div className="hidden sm:flex items-center gap-3">
            <ThemeToggle />
            <Link
              to="/login"
              className="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
              Entrar
            </Link>
            <Link
              to="/login?mode=register"
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-md shadow-primary/25 hover:bg-primary/90 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              Criar Conta
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>

          {/* Controles Mobile */}
          <div className="flex sm:hidden items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              type="button"
              className="inline-flex items-center justify-center rounded-xl p-2 text-muted-foreground hover:bg-muted/60 hover:text-foreground focus:outline-none"
              aria-label={mobileMenuOpen ? 'Fechar menu' : 'Abrir menu'}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Menu Retrátil Mobile */}
        {mobileMenuOpen && (
          <div className="sm:hidden border-b border-border bg-background/95 backdrop-blur-xl px-4 pt-3 pb-6 space-y-3">
            <a
              href="#solucao"
              onClick={() => setMobileMenuOpen(false)}
              className="block rounded-lg px-3 py-2 text-base font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Por que FreeCash
            </a>
            <a
              href="#features"
              onClick={() => setMobileMenuOpen(false)}
              className="block rounded-lg px-3 py-2 text-base font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Recursos
            </a>
            <a
              href="#telas"
              onClick={() => setMobileMenuOpen(false)}
              className="block rounded-lg px-3 py-2 text-base font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Demonstração
            </a>
            <a
              href="#depoimentos"
              onClick={() => setMobileMenuOpen(false)}
              className="block rounded-lg px-3 py-2 text-base font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Depoimentos
            </a>
            <a
              href="#faq"
              onClick={() => setMobileMenuOpen(false)}
              className="block rounded-lg px-3 py-2 text-base font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              FAQ
            </a>
            <div className="pt-2 border-t border-border flex flex-col gap-2">
              <Link
                to="/login"
                className="w-full text-center py-2.5 text-sm font-semibold text-foreground rounded-xl border border-border hover:bg-muted"
              >
                Acessar Conta
              </Link>
              <Link
                to="/login?mode=register"
                className="w-full text-center py-2.5 text-sm font-semibold text-primary-foreground bg-primary rounded-xl shadow-md"
              >
                Começar Gratuitamente
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* ─── 2. HERO SECTION ────────────────────────────────────────────── */}
      <section className="relative overflow-hidden pt-12 pb-20 md:pt-20 md:pb-32">
        {/* Glow de fundo decorativo */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 left-1/2 -z-10 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-gradient-to-tr from-primary/20 via-sky-500/10 to-transparent blur-3xl opacity-70"
        />

        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center text-center">
            {/* Pill de Destaque */}
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3.5 py-1 text-xs font-semibold text-primary mb-6 animate-pulse">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Suíte Financeira & Carteira ANBIMA Multi-Ativos</span>
            </div>

            {/* Headline Principal (H1) */}
            <h1 className="max-w-4xl text-3xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl text-foreground">
              O controle definitivo do seu patrimônio,{' '}
              <span className="bg-gradient-to-r from-primary via-sky-500 to-indigo-500 bg-clip-text text-transparent">
                sem planilhas quebradas.
              </span>
            </h1>

            {/* Subtítulo persuasivo */}
            <p className="mt-6 max-w-2xl text-base sm:text-lg text-muted-foreground leading-relaxed">
              Unifique a rotina do dia a dia com contas no formato Kanban, cartões de crédito e
              acompanhe sua carteira de ações e FIIs com cálculo de rentabilidade real e dividendos em
              efeito bola de neve.
            </p>

            {/* CTAs Duplos */}
            <div className="mt-8 flex flex-col sm:flex-row items-center gap-3.5 w-full sm:w-auto">
              <Link
                to="/login?mode=register"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-7 py-3.5 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all hover:-translate-y-0.5"
              >
                Começar Gratuitamente
                <ArrowRight className="h-5 w-5" aria-hidden="true" />
              </Link>
              <a
                href="#telas"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-7 py-3.5 text-base font-semibold text-foreground hover:bg-muted/70 transition-all"
              >
                Ver Telas do Sistema
              </a>
            </div>

            {/* Badges de Confiança */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-xs sm:text-sm text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
                <span>100% Privado e Seguro</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Lock className="h-4 w-4 text-emerald-500" />
                <span>Zero Venda de Dados</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Zap className="h-4 w-4 text-amber-500" />
                <span>Cotações em Tempo Real</span>
              </div>
            </div>

            {/* Mockup do Hero com Floating Cards */}
            <div className="mt-14 relative w-full max-w-5xl">
              {/* Moldura de Vidro da Aplicação */}
              <div className="rounded-2xl border border-border/80 bg-card/60 p-2 sm:p-3 shadow-2xl shadow-primary/10 backdrop-blur-xl">
                <div className="overflow-hidden rounded-xl border border-border bg-background">
                  {/* Top Bar do Browser Fake */}
                  <div className="flex h-9 items-center justify-between border-b border-border bg-muted/40 px-4">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full bg-destructive/60" />
                      <div className="h-2.5 w-2.5 rounded-full bg-amber-500/60" />
                      <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/60" />
                    </div>
                    <div className="rounded-md bg-muted px-4 py-0.5 text-[11px] font-mono text-muted-foreground">
                      freecash.local/dashboard
                    </div>
                    <div className="w-8" />
                  </div>

                  {/* Screenshot Principal */}
                  <img
                    src="/screenshots/01-dashboard.png"
                    alt="Visão Geral do Dashboard FreeCash"
                    className="w-full h-auto object-cover max-h-[540px]"
                    loading="eager"
                  />
                </div>
              </div>

              {/* Card Flutuante 1 (Efeito Bola de Neve / Dividendos) */}
              <div className="hidden lg:flex absolute -bottom-6 -left-6 items-center gap-3.5 rounded-2xl border border-border bg-card/90 p-4 shadow-xl backdrop-blur-md transition-transform hover:scale-105">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500">
                  <Sparkles className="h-6 w-6" />
                </div>
                <div className="text-left">
                  <div className="text-xs font-semibold text-muted-foreground">Proventos (12 meses)</div>
                  <div className="text-lg font-bold text-foreground">R$ 9.433,12</div>
                  <div className="text-[11px] font-medium text-emerald-500">Efeito Bola de Neve crescente</div>
                </div>
              </div>

              {/* Card Flutuante 2 (Pipeline Kanban) */}
              <div className="hidden lg:flex absolute -top-6 -right-6 items-center gap-3.5 rounded-2xl border border-border bg-card/90 p-4 shadow-xl backdrop-blur-md transition-transform hover:scale-105">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Kanban className="h-6 w-6" />
                </div>
                <div className="text-left">
                  <div className="text-xs font-semibold text-muted-foreground">Pipeline Kanban</div>
                  <div className="text-lg font-bold text-foreground">9 Contas no Mês</div>
                  <div className="text-[11px] font-medium text-primary">Liquidação com 1 clique</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── 3. PROBLEMA VS SOLUÇÃO ─────────────────────────────────────── */}
      <section id="solucao" className="border-t border-border bg-muted/20 py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h2 className="text-xs font-bold uppercase tracking-widest text-primary">
              A Evolução do seu Dinheiro
            </h2>
            <p className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl text-foreground">
              Por que abandonar planilhas e apps genéricos?
            </p>
            <p className="mt-4 text-muted-foreground text-base">
              Chega de perder fins de semana caçando fórmulas desconfiguradas ou de entregar seus dados
              bancários para aplicativos que vendem anúncios.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* O Jeito Tradicional (Problema) */}
            <div className="rounded-2xl border border-destructive/20 bg-card p-6 sm:p-8 shadow-sm relative overflow-hidden">
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
                  <XCircle className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-bold text-foreground">A Velha Maneira</h3>
              </div>
              <ul className="space-y-4 text-sm sm:text-base text-muted-foreground">
                <li className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <span>
                    <strong>Planilhas confusas:</strong> Fórmulas que quebram com um clique errado e
                    necessidade de digitação manual interminável.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <span>
                    <strong>Apps que vendem seus dados:</strong> Plataformas que usam seu extrato para
                    recomendar empréstimos e cartões indesejados.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <span>
                    <strong>Desconexão total:</strong> O saldo da conta corrente fica num app, a fatura
                    no banco e a carteira de ações na corretora.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <span>
                    <strong>Surpresas no fim do mês:</strong> Sem simulações prévias, você só descobre
                    que estourou o limite quando a fatura fecha.
                  </span>
                </li>
              </ul>
            </div>

            {/* O Jeito FreeCash (Solução) */}
            <div className="rounded-2xl border border-emerald-500/30 bg-card p-6 sm:p-8 shadow-lg shadow-emerald-500/5 relative overflow-hidden">
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-bold text-foreground">Com o FreeCash</h3>
              </div>
              <ul className="space-y-4 text-sm sm:text-base text-muted-foreground">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Automação inteligente:</strong> Conciliação de extratos bancários e faturas
                    PDF com processamento ágil e sem erro humano.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Privacidade absoluta:</strong> Seus dados ficam sob seu controle, isolados em
                    banco seguro com criptografia de ponta a ponta.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Visão 360° unificada:</strong> Do boleto da luz ao rendimento dos Fundos
                    Imobiliários, tudo no mesmo painel interativo.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Simulador preditivo:</strong> Antecipe o futuro financeiro de até 12 meses
                    antes de assumir qualquer nova dívida.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ─── 4. FEATURES / BENEFÍCIOS ───────────────────────────────────── */}
      <section id="features" className="py-20 md:py-28">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h2 className="text-xs font-bold uppercase tracking-widest text-primary">
              Poder & Flexibilidade
            </h2>
            <p className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl text-foreground">
              Projetado para quem leva dinheiro a sério
            </p>
            <p className="mt-4 text-muted-foreground text-base">
              Cada módulo foi desenvolvido para entregar clareza imediata e controle cirúrgico sobre as
              suas finanças.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
            {FEATURES.map((f, i) => {
              const Icon = f.icon;
              return (
                <div
                  key={i}
                  className="group relative rounded-2xl border border-border bg-card p-6 sm:p-7 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                      <Icon className="h-6 w-6" />
                    </div>
                    <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold text-muted-foreground">
                      {f.badge}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                    {f.title}
                  </h3>
                  <p className="mt-2.5 text-sm text-muted-foreground leading-relaxed">
                    {f.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ─── 5. SHOWCASE DE TELAS INTERATIVO ───────────────────────────── */}
      <section id="telas" className="border-y border-border bg-muted/30 py-20 md:py-28">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <h2 className="text-xs font-bold uppercase tracking-widest text-primary">
              Interface Real
            </h2>
            <p className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl text-foreground">
              Conheça a experiência por dentro
            </p>
            <p className="mt-4 text-muted-foreground text-base">
              Veja algumas das telas que tornam o FreeCash a ferramenta favorita de quem busca precisão.
            </p>
          </div>

          {/* Abas de Navegação */}
          <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
            {SCREEN_SHOWCASES.map((screen, idx) => (
              <button
                key={screen.id}
                onClick={() => setActiveScreenIndex(idx)}
                className={cn(
                  'rounded-xl px-4 py-2.5 text-sm font-semibold transition-all',
                  activeScreenIndex === idx
                    ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20 scale-105'
                    : 'bg-card text-muted-foreground border border-border hover:text-foreground hover:bg-muted/60'
                )}
              >
                {screen.label}
              </button>
            ))}
          </div>

          {/* Card Detalhado da Tela Ativa */}
          <div className="rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-xl">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              {/* Informações da Tela */}
              <div className="lg:col-span-4 space-y-4 text-left">
                <span className="inline-block rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">
                  {activeScreen.label}
                </span>
                <h3 className="text-2xl font-bold text-foreground">{activeScreen.title}</h3>
                <p className="text-sm sm:text-base text-muted-foreground leading-relaxed">
                  {activeScreen.description}
                </p>

                <div className="pt-2 space-y-2.5">
                  {activeScreen.highlights.map((item, i) => (
                    <div key={i} className="flex items-center gap-2.5 text-sm text-foreground">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>

                <div className="pt-4">
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-2 text-sm font-bold text-primary hover:underline"
                  >
                    Experimentar este módulo agora
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>

              {/* Preview da Imagem */}
              <div className="lg:col-span-8 overflow-hidden rounded-xl border border-border bg-background shadow-inner">
                <img
                  src={activeScreen.image}
                  alt={activeScreen.alt}
                  className="w-full h-auto object-cover max-h-[500px] transition-transform duration-300 hover:scale-[1.01]"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── 6. PROVA SOCIAL & NÚMEROS ─────────────────────────────────── */}
      <section id="depoimentos" className="py-20 md:py-28">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Métricas de Impacto */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center border-b border-border pb-16">
            <div>
              <div className="text-3xl sm:text-4xl font-black tracking-tight text-primary">100%</div>
              <div className="mt-1 text-xs sm:text-sm font-semibold text-muted-foreground uppercase">
                Privacidade & Dados Seus
              </div>
            </div>
            <div>
              <div className="text-3xl sm:text-4xl font-black tracking-tight text-primary">3 Níveis</div>
              <div className="mt-1 text-xs sm:text-sm font-semibold text-muted-foreground uppercase">
                Classificação ANBIMA
              </div>
            </div>
            <div>
              <div className="text-3xl sm:text-4xl font-black tracking-tight text-primary">&lt; 1s</div>
              <div className="mt-1 text-xs sm:text-sm font-semibold text-muted-foreground uppercase">
                Liquidação Kanban
              </div>
            </div>
            <div>
              <div className="text-3xl sm:text-4xl font-black tracking-tight text-primary">Zero</div>
              <div className="mt-1 text-xs sm:text-sm font-semibold text-muted-foreground uppercase">
                Anúncios ou Rastreamento
              </div>
            </div>
          </div>

          {/* Depoimentos */}
          <div className="mt-16 text-center max-w-3xl mx-auto mb-12">
            <h2 className="text-xs font-bold uppercase tracking-widest text-primary">Depoimentos</h2>
            <p className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl text-foreground">
              Quem usa, recomenda
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
            {TESTIMONIALS.map((t, idx) => (
              <div
                key={idx}
                className="flex flex-col justify-between rounded-2xl border border-border bg-card p-6 sm:p-7 shadow-sm"
              >
                <div>
                  {/* Estrelas */}
                  <div className="flex items-center gap-1 text-amber-500 mb-4">
                    {[...Array(t.rating)].map((_, i) => (
                      <Star key={i} className="h-4 w-4 fill-amber-500" />
                    ))}
                  </div>
                  <p className="text-sm sm:text-base text-muted-foreground leading-relaxed italic">
                    "{t.content}"
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-border flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-sm">
                    {t.avatar}
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-bold text-foreground">{t.name}</div>
                    <div className="text-xs text-muted-foreground">{t.role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── 7. FAQ INTERATIVO ─────────────────────────────────────────── */}
      <section id="faq" className="border-t border-border bg-muted/20 py-20 md:py-28">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-xs font-bold uppercase tracking-widest text-primary">Tire Suas Dúvidas</h2>
            <p className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl text-foreground">
              Perguntas Frequentes
            </p>
            <p className="mt-3 text-muted-foreground text-base">
              Tudo o que você precisa saber para começar a usar o FreeCash com total tranquilidade.
            </p>
          </div>

          <div className="space-y-4">
            {FAQS.map((faq, i) => {
              const isOpen = openFaqIndex === i;
              return (
                <div
                  key={i}
                  className="rounded-2xl border border-border bg-card transition-colors overflow-hidden"
                >
                  <button
                    onClick={() => setOpenFaqIndex(isOpen ? -1 : i)}
                    type="button"
                    className="flex w-full items-center justify-between p-5 sm:p-6 text-left focus:outline-none"
                    aria-expanded={isOpen}
                  >
                    <span className="text-base sm:text-lg font-bold text-foreground pr-4">
                      {faq.q}
                    </span>
                    <div
                      className={cn(
                        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition-transform duration-200',
                        isOpen && 'rotate-180 bg-primary/10 text-primary'
                      )}
                    >
                      <ChevronDown className="h-4 w-4" />
                    </div>
                  </button>

                  {isOpen && (
                    <div className="px-5 pb-6 sm:px-6 sm:pb-6 text-sm sm:text-base text-muted-foreground leading-relaxed border-t border-border/40 pt-4">
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ─── 8. CTA FINAL DE ALTA CONVERSÃO ───────────────────────────── */}
      <section className="relative overflow-hidden py-20 md:py-28">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-transparent via-primary/5 to-primary/10"
        />
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="relative rounded-3xl border border-primary/20 bg-card p-8 sm:p-12 md:p-16 text-center shadow-2xl shadow-primary/10 overflow-hidden">
            <div
              aria-hidden="true"
              className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/20 blur-3xl"
            />
            <div
              aria-hidden="true"
              className="absolute -left-20 -bottom-20 h-64 w-64 rounded-full bg-sky-500/20 blur-3xl"
            />

            <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-foreground">
              Pronto para ter clareza absoluta sobre seu patrimônio?
            </h2>
            <p className="mt-4 max-w-2xl mx-auto text-base sm:text-lg text-muted-foreground">
              Junte-se ao FreeCash hoje mesmo. Comece organizando suas contas e descubra o poder de
              controlar seus investimentos em um só lugar.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                to="/login?mode=register"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-8 py-4 text-base font-bold text-primary-foreground shadow-xl shadow-primary/25 hover:bg-primary/90 transition-all hover:scale-105"
              >
                Começar Agora Gratuitamente
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                to="/login"
                className="w-full sm:w-auto inline-flex items-center justify-center rounded-xl border border-border bg-card/80 px-8 py-4 text-base font-semibold text-foreground hover:bg-muted"
              >
                Já tenho uma conta
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ─── 9. FOOTER / RODAPÉ ────────────────────────────────────────── */}
      <footer className="border-t border-border bg-background py-12 text-sm text-muted-foreground">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            {/* Brand */}
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Wallet className="h-4 w-4" />
              </div>
              <span className="font-bold text-foreground text-base">FreeCash</span>
              <span className="text-xs text-muted-foreground">
                — Suíte de Gestão Financeira & Investimentos
              </span>
            </div>

            {/* Links */}
            <div className="flex flex-wrap items-center gap-6 text-sm">
              <a href="#solucao" className="hover:text-foreground transition-colors">
                Solução
              </a>
              <a href="#features" className="hover:text-foreground transition-colors">
                Recursos
              </a>
              <a href="#telas" className="hover:text-foreground transition-colors">
                Telas
              </a>
              <a href="#faq" className="hover:text-foreground transition-colors">
                FAQ
              </a>
              <Link to="/login" className="hover:text-foreground transition-colors">
                Acessar Sistema
              </Link>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-border/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
            <p>© {new Date().getFullYear()} FreeCash. Todos os direitos reservados.</p>
            <p className="flex items-center gap-1 text-muted-foreground">
              Desenvolvido com foco em segurança, privacidade e alta performance.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
