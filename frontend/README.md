# FreeCash — Frontend Application

[![React](https://img.shields.io/badge/React-19.2-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![TanStack Query](https://img.shields.io/badge/TanStack_Query-v5-FF4154?logo=react-query&logoColor=white)](https://tanstack.com/query)
[![ESLint](https://img.shields.io/badge/ESLint-v10-4B32C3?logo=eslint&logoColor=white)](https://eslint.org/)

Interface Single Page Application (SPA) do **FreeCash**, projetada com **React 19**, **Vite 6** e **Tailwind CSS v4**. Entrega alta reatividade, design system com suporte a Dark Mode, formulários com validação assíncrona tipada, visualização analítica com **ApexCharts** e governança de sessão ativa.

---

## 🧭 Mapa de Rotas e Telas

### 1. Rotas Públicas & Conversão
| Rota | Componente | Finalidade |
|---|---|---|
| `/landing`, `/inicio` | `LandingPage.jsx` | Apresentação institucional, diferenciais de mercado e captura |
| `/login` | `Login.jsx` | Autenticação de credenciais via cookies seguros |
| `/cadastro` | `Cadastro.jsx` | Fluxo de onboarding com validação de política de senhas |

### 2. Gestão Financeira & Planejamento
| Rota | Tela | Funcionalidade Principal |
|---|---|---|
| `/dashboard` | Dashboard Consolidado | Visão unificada de fluxo de caixa, despesas e KPIs mensais |
| `/contas-kanban` | Pipeline Kanban | Gestão de vencimentos com baixa por drag-and-drop |
| `/contas-pagar` | Contas a Pagar | Listagem, filtros e liquidação ágil com suporte a desfazer |
| `/contas-pagar/lote` | Cadastro em Lote | Tabela editável para importação massiva de despesas |
| `/cartoes` | Meus Cartões | Monitoramento de limites, faturas e projeção parcelada |
| `/simulador` | Simulador Sandbox | Projeção preditiva de 12 meses isolada em memória |
| `/horizonte-saldos` | Horizonte de Saldos | Grade de liquidez projetada dia a dia para o ano |
| `/calendario` | Calendário de Pagamentos | Calendário visual mensal de vencimentos e recebimentos |

### 3. Gestão Patrimonial & Investimentos
| Rota | Tela | Funcionalidade Principal |
|---|---|---|
| `/investimentos` | Dashboard de Investimentos | Alocação ANBIMA, patrimônio líquido e Efeito Bola de Neve |
| `/investimentos/ativos` | Meus Ativos | Posições em carteira com cotações em tempo real |
| `/investimentos/ativos/:id` | Detalhe de Posição | Visão isolada por ativo, rentabilidade e histórico |
| `/investimentos/balanceamento` | Aporte Eficiente | Algoritmo de rebalanceamento por metas percentuais |
| `/investimentos/historico` | Ledger de Operações | Livro contábil de compras, vendas e proventos |
| `/investimentos/classes` | Gestor ANBIMA | Manutenção da taxonomia de classes e categorias |

### 4. Governança e Administração
| Rota | Tela | Funcionalidade Principal |
|---|---|---|
| `/conta` | Minha Conta | Alteração de e-mail, encerramento de sessões e LGPD |
| `/admin/usuarios` | Gestão de Acessos | Auditoria de usuários e controle de suspensão de contas |
| `/admin/metricas` | BI de Plataforma | Indicadores analíticos de utilização do sistema |

---

## 🏗️ Padrões de Arquitetura do Frontend

- **Camada de Cache e Sincronização:** Implementada com **TanStack Query v5**, assegurando *optimistic updates*, revalidação inteligente e eliminação de *state waterfalls*.
- **Governança de Sessão & Inatividade:** Hook especializado `useInactivityTimer` acoplado ao `DashboardLayout`, monitorando eventos do usuário e acionando o `ModalInatividade` antes do encerramento forçado da sessão.
- **Formulários & Schemas:** Integração estrita entre **React Hook Form** e schemas **Zod**, validando políticas de segurança antes da submissão à API.
- **Design System Nativo:** Construído com classes utilitárias modernas do **Tailwind CSS v4** e ícones consistentes via **Lucide React**.

---

## 📂 Estrutura de Diretórios

```text
frontend/src/
├── components/
│   ├── auth/              # Componentes de segurança e controle de sessão
│   ├── ui/                # Átomos e moléculas do design system (Modal, Button, Table, etc.)
│   └── DashboardLayout.jsx# Layout estrutural autenticado com sidebar responsiva
├── config/                # Tabelas e documentação de ajuda contextual
├── context/               # Provedores globais (Autenticação JWT, Toasts)
├── hooks/                 # Custom hooks (temporizador de inatividade, media queries)
├── pages/                 # Visualizações e telas divididas por domínio
├── services/              # Camada de comunicação Axios com interceptors de segurança
├── App.jsx                # Declaração hierárquica de rotas e guardas de acesso
└── main.jsx               # Inicialização da aplicação React 19
```

---

## 🚀 Execução e Comandos

### Via Docker (Ambiente Integrado)

```bash
# Executar a suíte de testes no container
docker compose exec frontend npm run test

# Executar linter estático no container
docker compose exec frontend npm run lint
```

### Execução Local (Node.js 20+)

```bash
# 1. Instalar dependências
npm install

# 2. Iniciar servidor de desenvolvimento (Vite HMR)
npm run dev

# 3. Compilar para produção
npm run build
```

Acesso local após iniciar: `http://localhost:5173`.
