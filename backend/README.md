# FreeCash — Backend API

API RESTful construída em **Python 3.14 + Django 6** com **Django REST Framework**. É o núcleo de processamento financeiro: garante integridade dos dados, executa regras de precificação de investimentos, recalcula posições via Signals e gerencia conciliações bancárias.

---

## Tech Stack

| Tecnologia | Uso |
|---|---|
| Django 6 + DRF | Framework e engine de API |
| PostgreSQL 16 + psycopg3 | Banco de dados |
| djangorestframework-simplejwt | Auth stateless JWT via cookies HttpOnly |
| django-cors-headers | Liberação de CORS para o frontend React |
| TradingView Screener + CVM + Yahoo Finance (chart API) | Cotações diárias e histórico de ativos (scraping/HTTP direto, sem SDK) |
| openpyxl | Importação de extratos e exportação XLSX |
| pdfplumber + reportlab | Leitura de extratos/faturas em PDF e geração de relatórios |
| cryptography | Criptografia do backup `.fcbk` |
| whitenoise | Servir estáticos diretamente no container da API |

---

## Apps Django

### `core` — Módulo Financeiro Central

Gerencia todo o fluxo de caixa pessoal do usuário.

**Modelos principais:**
- `Conta` — Transação financeira (receita ou despesa) com data de vencimento, realização, categoria e cartão vinculado
- `CartaoCredito` — Cartão com limite, dia de fechamento/vencimento, cor e ícone
- `Categoria` — Classificação de transações por tipo (Receita/Despesa/Investimento)
- `ConfigUsuario` — Preferências e configurações por usuário
- `ExtratoImportado` + `LinhaExtrato` — Pipeline de importação de extratos bancários

A lista de endpoints abaixo é organizada por domínio de negócio — não existe mais um `urls.py` por app; tudo é registrado em `freecash/urls.py`.

**Autenticação:**
```
POST   /api/register/                          Cadastro de usuário
POST   /api/token/                             Login (JWT)
POST   /api/token/refresh/                     Renovar token
POST   /api/token/clear/                       Logout
```

**Dashboards e relatórios:**
```
GET    /api/dashboard/                         KPIs + gráficos do mês
GET    /api/dashboard/executivo/               Dashboard executivo (BI, histórico patrimonial de 12 meses)
GET    /api/relatorios/dre/?ano=2026           DRE anual
```

**Financeiro (usado pelo frontend):**
```
GET/POST/PUT/DELETE   /api/financeiro/cartoes/               CRUD de cartões
GET/POST/PUT/DELETE   /api/financeiro/contas-pagar/          CRUD de contas a pagar
PUT    /api/financeiro/contas-pagar/{id}/pagar/               Marcar como paga
PUT    /api/financeiro/contas-pagar/{id}/desfazer-pagamento/  Desfazer pagamento
POST   /api/financeiro/contas-pagar/lote/                     Cadastro em lote
GET/POST/PUT/DELETE   /api/financeiro/receitas/               CRUD de receitas
GET    /api/financeiro/transacoes/                            Extrato consolidado (somente leitura)
GET/POST/PUT/DELETE   /api/financeiro/compras-cartao/         CRUD de compras de cartão (conciliação)
GET/POST/PUT   /api/configuracoes/contas-bancarias/           Contas bancárias/cartões cadastrados
POST   /api/configuracoes/contas-bancarias/{id}/toggle_ativo/ Ativar/inativar
```

**CRUDs legados (ainda existem no código; `/api/cartoes/` está sobreposto por `/api/financeiro/cartoes/`, que é o que o frontend consome hoje):**
```
GET/POST/PATCH/DELETE  /api/contas/            CRUD de transações
GET/POST/PATCH/DELETE  /api/cartoes/           CRUD de cartões (rota antiga, sem uso confirmado no frontend)
GET/POST/PATCH/DELETE  /api/categorias/        CRUD de categorias
```

**Ferramentas:**
```
GET/POST   /api/ferramentas/exportar/          Export XLSX/CSV/PDF/.fcbk
POST       /api/ferramentas/importar/          Import backup .fcbk
POST       /api/ferramentas/importar-extrato/  Import de fatura em PDF
GET        /api/ferramentas/conciliacao/       Lista itens pendentes de conciliação
POST       /api/ferramentas/conciliacao/processar/  Processa conciliação bancária
```

**Tarefas internas (management commands, não são endpoints HTTP):**
- `update_quotes` — atualiza cotações via TradingView Screener
- `update_portfolio_history` — grava snapshot diário/mensal da carteira (`CarteiraHistorico`)
- `populate_investments` — popula dados iniciais de investimentos

---

### `investimento` — Módulo de Gestão de Ativos

Cobre toda a matemática patrimonial e alocação de ativos.

**Hierarquia ANBIMA (3 níveis):**
```
ClasseAtivo (Renda Fixa, Renda Variável, Criptoativos...)
  └── CategoriaAtivo (CDB/RDB, Ações Brasil, FII de Tijolo...)
        └── SubcategoriaAtivo (Tesouro Selic, PETR4, HGLG11...)
              └── Ativo (ticker, preço médio, quantidade acumulada)
```

**Modelos principais:**
- `Ativo` — Ativo individual com ticker, subcategoria ANBIMA, meta de alocação, preço médio e quantidade (mantidos por Signal)
- `Transacao` — Operação de Compra (C), Venda (V) ou Provento (D) com quantidade, preço unitário e taxas (serializada como "TransacaoInvestimento")
- `Cotacao` — Histórico de preços diários por ativo
- `CarteiraHistorico` — Snapshot patrimonial periódico, usado no dashboard executivo

**Signals (`signals.py`):** popula a árvore ANBIMA para usuários novos e recalcula preço médio/quantidade do `Ativo` a cada criação, edição ou remoção de `Transacao`.

**Endpoints principais:**
```
GET/POST/PATCH/DELETE  /api/investimentos/ativos/
POST   /api/investimentos/ativos/atualizar-cotacoes/       Sincroniza cotações de todos os ativos
POST   /api/investimentos/ativos/{id}/atualizar/           Sincroniza histórico (30 dias) de um ativo

GET/POST/PATCH/DELETE  /api/investimentos/transacoes/

GET    /api/investimentos/dashboard/           Patrimônio, rentabilidade, alocação, snowball
GET/POST   /api/investimentos/balanceamento/   Cálculo de aporte ideal por ativo

GET/POST/PATCH/DELETE  /api/investimentos/classes/
GET/POST/PATCH/DELETE  /api/investimentos/categorias/
GET/POST/PATCH/DELETE  /api/investimentos/subcategorias/
```

---

## Desenvolvimento Local

### 1. Ambiente Virtual

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 2. Dependências

```bash
pip install -r requirements.txt
```

### 3. Variáveis de Ambiente

```bash
cp ../.env_example .env
```

Variáveis mínimas para banco local:
```env
DB_NAME=freecash_db
DB_USER=freecash_user
DB_PASS=freecash_pass
DB_HOST=localhost
DB_PORT=5432
```

### 4. Banco e Superusuário

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Rodar

```bash
python manage.py runserver 127.0.0.1:8000
```

Painel admin disponível em http://127.0.0.1:8000/admin/

---

## Testes

```bash
# Todos os testes
python manage.py test

# Suite específica
python manage.py test investimento.tests
python manage.py test core.tests
```
