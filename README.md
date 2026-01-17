# FreeCash

**FreeCash** é uma aplicação web completa para gestão financeira pessoal e controle de investimentos.
Desenvolvida com **Django** e **TailwindCSS**, oferece uma interface moderna e responsiva para acompanhar receitas, despesas e a evolução do seu patrimônio em um só lugar.

---

## 🚀 Funcionalidades Principais

### 1. Controle Financeiro (`Core`)
-   **Dashboard Analítico**: Visão clara de receitas, despesas e saldo do mês, com gráficos de evolução e breakdown por categoria.
-   **Gestão de Contas**: Controle de contas a pagar (pagas/pendentes) com alertas visuais.
-   **Transações**: Registro rápido de receitas e despesas, categorização dinâmica e filtros avançados.
-   **Importação/Exportação**: Ferramenta robusta para backup (XLSX) e importação de dados legados ou backups anteriores.
-   **Onboarding Automático**: Novos usuários já começam com categorias e configurações padrão prontas para uso.

### 2. Gestão de Investimentos (`Investimento`)
-   **Classificação Hierárquica (ANBIMA)**: Organização profissional de ativos em 3 níveis (**Classe > Categoria > Subcategoria**), ex: *Renda Fixa > Títulos Públicos > Tesouro Selic*.
-   **Carteira Multi-Ativos**: Suporte nativo para:
    -   **Renda Variável**: Ações, FIIs, ETFs, BDRs.
    -   **Renda Fixa**: CDBs, Tesouro Direto, LCI/LCA (com campos para Vencimento, Emissor, Indexador e Taxa).
    -   **Criptoativos**: Bitcoin, Ethereum, Stablecoins.
    -   **Fundos e Outros**: Flexibilidade para diversos tipos de investimento.
-   **Controle de Posição**:
    -   Cálculo automático de **Preço Médio (PM)** e **Quantidade** baseado no histórico.
    -   Registro de **Compras**, **Vendas** e **Proventos** (Dividendos/JCP).
    -   Atualização de saldo em tempo real via *Django Signals*.
-   **Dashboard de Investimentos**: KPI de Patrimônio Total e lista detalhada de ativos com rentabilidade e alocação.

---

## 🛠 Stack Tecnológico

-   **Backend**: Python 3.12+, Django 6.0+
-   **Banco de Dados**: PostgreSQL
-   **Frontend**: HTML5, Django Templates, **TailwindCSS** (via CDN), Chart.js
-   **Infraestrutura**: Docker & Docker Compose
-   **Ferramentas**: Pandas & OpenPyXL (manipulação de dados), Dotenv (configuração)

---

## 📂 Estrutura do Projeto

```text
freecash/
├── core/                   # Módulo Financeiro (Receitas, Despesas, Dashboard)
│   ├── models.py           # Modelos de domínio (Categoria, Conta, Transacao)
│   ├── services/           # Lógica de negócio (Importação, Exportação)
│   ├── templates/          # Templates HTML do módulo financeiro
│   └── views/              # Controladores das interfaces
├── investimento/           # Módulo de Investimentos (Novo)
│   ├── models.py           # Ativo, Transacao, ClasseAtivo, SubcategoriaAtivo
│   ├── signals.py          # Automação de cálculos e criação de hierarquia
│   ├── templates/          # Telas de Investimento (Listas, Forms, Dashboard)
│   │   └── investimento/
│   └── views.py            # Lógica de visualização de investimentos
├── freecash/               # Configurações globais (settings.py, urls.py)
├── static/                 # Arquivos estáticos (CSS, JS, Imagens)
├── media/                  # Uploads de usuários
└── docker-compose.yml      # Orquestração de containers
```

---

## ⚡ Como Rodar o Projeto

### Opção A: Com Docker (Recomendado)

Garanta que você tem o **Docker** e **Docker Compose** instalados.

1.  **Configure o ambiente**:
    ```bash
    cp .env_example .env
    # Edite o .env se necessário (as configs padrão costumam funcionar no Docker)
    ```

2.  **Suba os containers**:
    ```bash
    docker-compose up --build
    ```
    *Isso irá construir a imagem, subir o banco PostgreSQL e iniciar o servidor Django.*

3.  **Acesse**:
    Abra `http://localhost:8000` no seu navegador.

### Opção B: Localmente (Manual)

1.  **Crie e ative o ambiente virtual**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    ```

2.  **Instale as dependências**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure o banco de dados**:
    Certifique-se de ter um PostgreSQL rodando e ajuste o `.env` com as credenciais (`DB_HOST=localhost`).

4.  **Execute as migrações e crie um superusuário**:
    ```bash
    python manage.py migrate
    python manage.py createsuperuser
    ```

5.  **Rode o servidor**:
    ```bash
    python manage.py runserver
    ```

---

## 🧪 Testes e Comandos Úteis

-   **Rodar Testes**:
    ```bash
    python manage.py test core investimento
    ```
-   **Popular Investimentos (Correção de Hierarquia)**:
    Se você já tem usuários antigos e precisa gerar a estrutura de investimentos:
    ```bash
    python manage.py populate_investments
    ```
-   **Shell Interativo**:
    ```bash
    python manage.py shell
    ```

---

## 📝 Notas de Desenvolvimento

-   **Padrão de Código**: O projeto segue a PEP-8 e utiliza Type Hints onde possível.
-   **Design System**: O frontend utiliza classes utilitárias do TailwindCSS para estilização rápida e consistente.
-   **Automação**: O cadastro de ativos utiliza `signals` para garantir que o saldo nunca fique dessincronizado das transações.
