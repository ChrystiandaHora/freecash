# ⚙️ FreeCash - Backend API

O **FreeCash Backend** é uma API RESTful robusta desenvolvida em **Python 3.12+** utilizando o framework **Django 6.0** e o **Django REST Framework (DRF)**. É o núcleo de processamento financeiro do ecossistema, responsável por garantir a integridade dos dados, executar regras complexas de precificação de investimentos e gerenciar conciliações bancárias.

---

## 🛠 Tech Stack & Bibliotecas Chave

*   **Core**: [Django 6.0+](https://djangoproject.com/) & [Django REST Framework (DRF)](https://www.django-rest-framework.org/)
*   **Banco de Dados**: [PostgreSQL 16](https://www.postgresql.org/) com drivers assíncronos de alta performance `psycopg3`.
*   **Autenticação**: `djangorestframework-simplejwt` para autenticação stateless baseada em tokens JWT (JSON Web Tokens).
*   **Integração com Mercado**: `yfinance` (Yahoo Finance API) para coleta diária e em tempo real de preços históricos e de fechamento dos ativos da carteira.
*   **Manipulação de Dados**: `pandas` e `openpyxl` para o pipeline de importação inteligente de extratos bancários (Nubank, Itaú, Banco Inter, etc.) e exportação de backups em XLSX.
*   **Relatórios & Arquivos**: `pdfplumber` para leitura estruturada de extratos e `reportlab` para relatórios consolidados em PDF.
*   **Serviço de Estáticos**: `whitenoise` para servir arquivos estáticos de forma ágil diretamente no container da API.

---

## 📂 Arquitetura de Módulos (Django Apps)

O backend do FreeCash é dividido de forma modular em duas aplicações centrais de negócio:

### 1. `core` (Módulo Financeiro Central)
Responsável pelo fluxo de caixa pessoal do usuário.
*   **Dashboard de Fluxo de Caixa**: Consolidação mensal de receitas e despesas.
*   **Contas a Pagar/Receber**: Controle de prazos e alertas visuais de contas.
*   **Cartões de Crédito**: Gestão de faturas agendadas, limites de cartões e datas de fechamento/vencimento.
*   **Módulo de Importação**: Engine de importação e mapeamento automático de extratos bancários brutos em transações.

### 2. `investimento` (Módulo de Gestão de Ativos)
Responsável por toda a matemática patrimonial e alocação de ativos.
*   **Taxonomia ANBIMA**: Hierarquização estrita de 3 níveis para classes, categorias e subcategorias de ativos.
*   **Carteira Multi-Ativos**: Suporte nativo para Renda Fixa parametrizada (indexadores: CDI, IPCA, Selic, Pré-fixado), Renda Variável (Ações, FIIs, ETFs) e Criptoativos.
*   **Signals & Recalculators (`signals.py`)**: 
    *   `criar_classificacao_padrao`: Popula automaticamente toda a árvore ANBIMA quando um novo usuário se cadastra.
    *   `atualizar_ativo_apos_transacao`: Recomputa o **Preço Médio (PM)** de aquisição e a **Quantidade** real sempre que transações são criadas, editadas ou removidas.
*   **Yahoo Finance Sync**: Integração para cotações e cálculo em tempo real de rentabilidade acumulada de carteira.

---

## ⚡ Desenvolvimento Local

### Pré-requisitos
*   [Python 3.12+](https://www.python.org/)
*   [PostgreSQL 16](https://www.postgresql.org/) (rodando localmente ou via container)

### 1. Configurar Ambiente Virtual
Navegue até a pasta `backend` (ou na raiz do projeto) e execute:
```bash
python3 -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
```

### 2. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz do backend (ou configure no host) com base nas variáveis:
```env
DB_NAME=freecash_db
DB_USER=freecash_user
DB_PASS=freecash_pass
DB_HOST=localhost
DB_PORT=5432
```

### 4. Executar Migrações e Inicializar Banco
```bash
python manage.py migrate
```

### 5. Popular Banco de Dados (Dados Iniciais)
O FreeCash conta com um comando customizado para criar a estrutura ANBIMA padrão:
```bash
python manage.py populate_investments
```

### 6. Criar Superusuário Administrativo
```bash
python manage.py createsuperuser
```

### 7. Executar o Servidor de Desenvolvimento
```bash
python manage.py runserver 127.0.0.1:8000
```
O painel administrativo do Django estará disponível em `http://127.0.0.1:8000/admin/`.

---

## 🧪 Testes Automatizados

Para executar os testes unitários e de integração locais para validar o fluxo financeiro e de investimentos:
```bash
python manage.py test
```
Para obter detalhes de uma suite específica:
```bash
python manage.py test investimento.tests
```
