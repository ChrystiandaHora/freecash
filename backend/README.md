# FreeCash — Backend API

API RESTful construída em **Python 3.12 + Django 6** com **Django REST Framework**. É o núcleo de processamento financeiro: garante integridade dos dados, executa regras de precificação de investimentos, recalcula posições via Signals e gerencia conciliações bancárias.

---

## Tech Stack

| Tecnologia | Uso |
|---|---|
| Django 6 + DRF | Framework e engine de API |
| PostgreSQL 16 + psycopg3 | Banco de dados com driver assíncrono |
| djangorestframework-simplejwt | Auth stateless JWT via cookies HttpOnly |
| yfinance | Cotações diárias e em tempo real (Yahoo Finance) |
| pandas + openpyxl | Importação de extratos bancários e exportação XLSX |
| pdfplumber + reportlab | Leitura de extratos PDF e geração de relatórios |
| whitenoise | Servir estáticos diretamente no container da API |

---

## Apps Django

### `core` — Módulo Financeiro Central

Gerencia todo o fluxo de caixa pessoal do usuário.

**Modelos principais:**
- `Conta` — Transação financeira (receita ou despesa) com data de vencimento, realização, categoria e cartão vinculado
- `CartaoCredito` — Cartão com limite, dia de fechamento/vencimento, cor e ícone
- `Categoria` — Classificação de transações por tipo (Receita/Despesa/Investimento)
- `ExtratoImportado` + `LinhaExtrato` — Pipeline de importação de extratos bancários

**Endpoints principais:**
```
POST   /api/register/                          Cadastro de usuário
POST   /api/token/                             Login (JWT)
POST   /api/token/refresh/                     Renovar token
POST   /api/token/clear/                       Logout

GET    /api/dashboard/                         KPIs + gráficos do mês
GET    /api/relatorios/dre/?ano=2026           DRE anual

GET/POST/PATCH/DELETE  /api/contas/            CRUD de transações
GET/POST/PATCH/DELETE  /api/cartoes/           CRUD de cartões
GET/POST/PATCH/DELETE  /api/categorias/        CRUD de categorias

GET/POST   /api/ferramentas/exportar/          Export XLSX/CSV/PDF/.fcbk
POST       /api/ferramentas/importar/          Import backup .fcbk
```

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
- `TransacaoInvestimento` — Operação de Compra (C), Venda (V) ou Provento (D) com quantidade, preço unitário e taxas

**Signals (`signals.py`):**
- `criar_classificacao_padrao` — Popula toda a árvore ANBIMA ao criar um novo usuário
- `atualizar_ativo_apos_transacao` — Recalcula Preço Médio e Quantidade acumulada em toda criação, edição ou remoção de transação

**Endpoints principais:**
```
GET/POST/PATCH/DELETE  /api/investimentos/ativos/
POST   /api/investimentos/ativos/atualizar-cotacoes/

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
