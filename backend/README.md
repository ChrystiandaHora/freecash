# FreeCash — Backend API Engine

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/Django_REST_Framework-3.15-red?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![JWT](https://img.shields.io/badge/Auth-SimpleJWT_HttpOnly-black)](https://django-rest-framework-simplejwt.readthedocs.io/)

Núcleo de serviços e inteligência financeira do **FreeCash**. A API é construída sobre **Python 3.14**, **Django 6** e **Django REST Framework**, garantindo integridade transacional ACID, segregação de inquilinos (*multi-tenancy*), automação de rotinas contábeis via Signals e integração com fontes oficiais de mercado.

---

## 🏛️ Arquitetura de Domínios

A aplicação é dividida em dois domínios de negócio principais:

### 1. `core` — Finanças Pessoais & Governança de Caixa
- **Ciclo de Liquidez:** Gestão de receitas, despesas fixas/avulsas e contas a pagar com suporte a parcelamentos.
- **Cartões de Crédito:** Controle de limites, datas de corte/vencimento e conciliação de faturas em PDF via `pdfplumber`.
- **DRE & Relatórios:** Apuração contábil anual (Receita Operacional, EBITDA, Margem Líquida) e projeção de fluxo de caixa.
- **Segurança & Identidade:** Autenticação stateless via cookies `HttpOnly`, invalidação de sessões remotas e auditoria administrativa.

### 2. `investimento` — Gestão Patrimonial & Alocação Multi-Ativos
- **Taxonomia ANBIMA (3 Níveis):** Hierarquia rigorosa (*Classe → Categoria → Subcategoria → Ativo*).
- **Múltiplas Custódias:** Segregação de posições por instituição/corretora sem distorção do preço médio fiscal consolidado.
- **Signals Transacionais:** Recálculo instantâneo de quantidade acumulada, custo e preço médio a cada operação (Compra, Venda, Provento, Transferência).
- **Algoritmo de Aporte Eficiente:** Cálculo analítico de compras para convergência da carteira à alocação alvo estipulada pelo investidor.
- **Cotações Resilientes:** Provedores de mercado (TradingView Screener, CVM e Yahoo Finance) implementados via HTTP nativo (`urllib`), eliminando dependências de bibliotecas instáveis de scraping.

---

## 🔌 Principais Endpoints da API

Todas as rotas são expostas sob o prefixo `/api/` e requerem autenticação JWT (exceto rotas de onboarding):

| Grupo | Método | Rota | Descrição |
|---|:---:|---|---|
| **Autenticação** | `POST` | `/api/token/` | Autenticação e emissão de cookie `HttpOnly` |
| | `POST` | `/api/token/refresh/` | Rotação e renovação do access token |
| | `POST` | `/api/token/clear/` | Logout e revogação de tokens ativos |
| **Financeiro** | `GET/POST` | `/api/dashboard/` | Métricas consolidadas e fluxo diário do mês |
| | `GET/POST/PUT` | `/api/financeiro/contas-pagar/` | Ciclo operacional de contas a pagar |
| | `POST` | `/api/financeiro/contas-pagar/lote/` | Inclusão em massa de lançamentos |
| | `GET/POST/PUT` | `/api/financeiro/cartoes/` | Gestão de limites e cartões de crédito |
| | `GET` | `/api/financeiro/transacoes/` | Extrato cronológico com agrupamento diário |
| **Investimentos**| `GET` | `/api/investimentos/dashboard/` | Patrimônio, alocação ANBIMA e snowball |
| | `GET/POST` | `/api/investimentos/ativos/` | Posições consolidadas e detalhe de ativos |
| | `POST` | `/api/investimentos/ativos/atualizar-cotacoes/` | Sincronização em lote com provedores |
| | `GET/POST` | `/api/investimentos/balanceamento/` | Cálculo preditivo de aporte ideal |
| | `GET/POST` | `/api/investimentos/carteiras/` | Gestão de custódias por corretora |
| **Ferramentas** | `POST` | `/api/ferramentas/importar-extrato/` | Parsing e conciliação de faturas PDF |
| | `GET/POST` | `/api/ferramentas/exportar/` | Exportação de dados e backup criptografado `.fcbk` |

---

## ⚙️ Execução e Desenvolvimento

### Via Docker (Padrão de Produção e Desenvolvimento)

A forma recomendada de executar e interagir com o backend é via containers:

```bash
# Iniciar a pilha completa (PostgreSQL + Backend + Frontend)
docker compose up -d

# Executar migrações do banco de dados
docker compose exec backend python manage.py migrate

# Criar superusuário administrativo
docker compose exec backend python manage.py createsuperuser

# Popular banco com dados analíticos realistas
docker compose exec backend python create_dummy_data.py
```

### Execução Local (Fora do Container)

Caso prefira rodar localmente com Python 3.12+:

```bash
# 1. Ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Instalar dependências de compilação e runtime
pip install -r requirements.txt

# 3. Executar servidor de desenvolvimento
python manage.py runserver 127.0.0.1:8000
```

---

## 🧪 Qualidade e Testes Automatizados

A API conta com ampla cobertura de testes integrados e unitários sobre PostgreSQL, validando invariantes fiscais e isolamento multi-inquilino:

```bash
# Executar todos os testes da aplicação
docker compose exec backend python manage.py test

# Testar exclusivamente o domínio de investimentos
docker compose exec backend python manage.py test investimento.tests

# Testar exclusivamente o domínio financeiro
docker compose exec backend python manage.py test core.tests
```
