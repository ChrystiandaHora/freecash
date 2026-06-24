# FreeCash — Frontend

SPA (Single Page Application) construída em **React 19 + Vite 6**, com **Tailwind CSS v4** para estilização ultra-veloz e **TanStack React Query** para sincronização inteligente com a API.

---

## Tech Stack

| Tecnologia | Uso |
|---|---|
| React 19 + Vite 6 | SPA com HMR e build otimizado |
| Tailwind CSS v4 | Estilização nativa baseada em CSS moderno |
| TanStack React Query | Cache, sincronização e invalidação de estado com a API |
| React Router Dom v7 | Roteamento SPA com rotas protegidas |
| React Hook Form + Zod | Formulários com validação tipada no cliente |
| ApexCharts | Gráficos interativos (área, donut, barra, scatter, radial) |
| Lucide React | Biblioteca unificada de ícones vetoriais |
| Axios | HTTP client com interceptors JWT |

---

## Páginas

### Geral
| Rota | Página | Descrição |
|---|---|---|
| `/dashboard` | Dashboard | KPIs financeiros, fluxo de caixa diário, projeção 6 meses |
| `/relatorios` | Relatórios | DRE anual, fluxo operacional, heatmap de sazonalidade |

### Financeiro
| Rota | Página | Descrição |
|---|---|---|
| `/contas-pagar` | Contas a Pagar | CRUD com status inteligente e pagamento rápido |
| `/contas-pagar/lote` | Cadastro em Lote | Tabela editável para múltiplas contas |
| `/contas-kanban` | Pipeline Kanban | Quadro drag-and-drop com 5 colunas de status |
| `/cartoes` | Meus Cartões | Gauge de limite, histórico por cartão |
| `/receitas` | Receitas | Controle de receitas previstas e realizadas |
| `/transacoes` | Transações | Extrato cronológico agrupado por dia |

### Investimentos
| Rota | Página | Descrição |
|---|---|---|
| `/investimentos` | Dashboard | Patrimônio, alocação, árvore ANBIMA, snowball effect |
| `/investimentos/ativos` | Meus Ativos | Tabela completa de carteira com cotações |
| `/investimentos/ativos/:id` | Detalhe do Ativo | Posição, rentabilidade e histórico por ativo |
| `/investimentos/balanceamento` | Balanceamento | Sliders de meta e cálculo de aporte ideal |
| `/investimentos/historico` | Histórico | Ledger de compras, vendas e proventos |
| `/investimentos/classes` | Classes ANBIMA | CRUD da hierarquia de 3 níveis |

### Ferramentas e Ajustes
| Rota | Página | Descrição |
|---|---|---|
| `/importar` | Importar Backup | Drag-and-drop de arquivo `.fcbk` |
| `/compras-cartao` | Compras Cartão | Importação de PDF de faturas |
| `/backup` | Backup/Exportar | Export XLSX/CSV/PDF/.fcbk com senha |
| `/pagamentos` | Ajustes Pagamentos | Gestão de cartões e contas bancárias |

---

## Estrutura

```
src/
├── components/
│   ├── ui/                 # Componentes atômicos (Button, Card, Modal, Badge, DataTable...)
│   └── DashboardLayout.jsx # Layout mestre com sidebar colapsável e navbar
├── context/
│   ├── AuthProvider.jsx    # Estado de autenticação JWT + interceptors Axios
│   └── ToastContext.jsx    # Sistema de notificações (toasts)
├── pages/                  # 20+ telas da aplicação
├── services/
│   ├── api.js              # Instância Axios configurada
│   └── queries/            # Custom hooks React Query por domínio de negócio
├── App.jsx                 # Roteamento + provedores globais
└── main.jsx                # Ponto de entrada
```

---

## Desenvolvimento Local

### Pré-requisitos
Node.js 20+ instalado.

### 1. Instalar dependências

```bash
npm install
```

### 2. Variável de ambiente

Crie `.env` na raiz do `frontend/`:
```env
VITE_API_URL=http://localhost:8000
```

### 3. Servidor de desenvolvimento

```bash
npm run dev
```

Acesse http://localhost:5173.

---

## Scripts

| Comando | Descrição |
|---|---|
| `npm run dev` | Servidor de desenvolvimento com HMR |
| `npm run build` | Build otimizado para produção em `dist/` |
| `npm run preview` | Preview do build de produção localmente |
| `npm run lint` | Análise estática com ESLint |
