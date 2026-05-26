# 💸 FreeCash

**FreeCash** é uma solução completa de nível profissional para gestão financeira pessoal e controle avançado de investimentos. A aplicação combina um poderoso ecossistema de retaguarda (Backend) em **Django 6.0** com uma interface de usuário dinâmica, reativa e moderna em **React 19** e **Tailwind CSS v4**.

Desenvolvido para oferecer controle patrimonial absoluto, o FreeCash não se limita a apenas registrar entradas e saídas; ele integra a consolidação de carteiras multi-ativos com as normas padrão de mercado, cotações atualizadas via integração de mercado e automação total com containers Docker e inteligência de orquestração de rede local.

---

## 🚀 Funcionalidades Principais

### 1. Gestão Financeira Pessoal (`core`)
*   **Dashboard de Fluxo de Caixa**: Visão analítica de receitas, despesas e saldo líquido consolidado no mês, com suporte a breakdowns gráficos e categorização de despesas.
*   **Controle de Contas a Pagar/Receber**: Registro de compromissos agendados por data de vencimento com alertas visuais intuitivos para contas vencidas ou próximas do prazo.
*   **Sistema de Faturas de Cartão de Crédito**: Módulo dedicado para cartões com dias específicos de fechamento e vencimento, automatizando o agrupamento de despesas e controle de limite.
*   **Importação Inteligente de Extratos**: Processamento e conciliação de extratos bancários gerados por grandes instituições (Nubank, Banco Inter, Itaú, Bradesco, etc.) em formatos tabulares, mapeando automaticamente as linhas de extrato para transações financeiras.
*   **Backup e Exportação**: Mecanismos integrados para exportar bases históricas de usuários em planilhas XLSX e importar backups legados de forma íntegra.

### 2. Gestão Avançada de Investimentos (`investimento`)
*   **Hierarquia de Ativos ANBIMA (3 Níveis)**: Organização estrutural estrita para alocação de carteira de investimentos:
    *   **Nível 1 (Classe)**: Renda Fixa, Renda Variável, Multimercado, Cambial, Criptoativos.
    *   **Nível 2 (Categoria)**: Pós-fixado, Inflação (IPCA), Pré-fixado, Ações, FIIs, ETFs, Moedas, Moedas Digitais.
    *   **Nível 3 (Subcategoria)**: Tesouro Selic, CDB/RDB, LCI/LCA, Ações Brasil, BDRs, FII de Tijolo, FII de Papel, Bitcoin, Ethereum, etc.
*   **Carteira Multi-Ativos**: Suporte nativo e parametrizado para Renda Fixa (Vencimento, Emissor, Indexador e Taxa), Renda Variável, Criptoativos e Fundos.
*   **Cálculo Automático de Posição**: Controle nativo de **Preço Médio (PM)** e **Quantidade Acumulada** baseado em compras e vendas com compensações dinâmicas de taxas e corretagem.
*   **Gestão de Proventos**: Registro e rastreamento de dividendos, JCP (Juros sobre Capital Próprio) e rendimentos recebidos, com impacto direto na rentabilidade histórica do ativo.
*   **Cotações em Tempo Real**: Integração técnica com APIs de mercado financeiro (Yahoo Finance via `yfinance`) para atualizar preços de fechamento diários e calcular a rentabilidade real comparada com o custo médio.

### 3. Dynamic Port Orchestrator (`run.sh` & `run.py`)
*   **Zero-Configuration Dev**: Script de orquestração local que analisa automaticamente se as portas padrão (`5432` para PostgreSQL, `8000` para Django, `5173` para React) estão ocupadas por outros processos no Host.
*   **Resolução Dinâmica**: Em caso de conflito, o FreeCash remapeia automaticamente os serviços para as próximas portas disponíveis e gera dinamicamente as variáveis correspondentes no arquivo `.env.docker`, garantindo que os containers e a API se comuniquem perfeitamente sem qualquer intervenção manual do desenvolvedor. Disponível em versão Bash universal `./run.sh` (com zero dependências do host) e Python `run.py`.

---

## 🛠 Tech Stack

O ecossistema do FreeCash é construído sobre ferramentas modernas e estáveis de desenvolvimento de software:

### Backend (API & Lógica)
*   **Linguagem & Framework**: `Python 3.12+` e `Django 6.0+`
*   **Banco de Dados**: `PostgreSQL 16` via driver assíncrono `psycopg3`
*   **API Engine**: `Django REST Framework (DRF)` para endpoints RESTful de alta performance.
*   **Segurança**: `djangorestframework-simplejwt` para autenticação baseada em tokens JWT.
*   **Integração de Mercado**: `yfinance` para consultas de cotações financeiras globais e nacionais em tempo real.
*   **Processamento de Dados**: `pandas` e `openpyxl` para manipulação, importação e exportação de planilhas.
*   **Engine de PDFs**: `reportlab` e `pdfplumber` para geração e leitura de relatórios financeiros e extratos.
*   **Serviço de Arquivos**: `whitenoise` para servir arquivos estáticos otimizados diretamente pelo container Django.

### Frontend (Interface de Usuário)
*   **Linguagem & Framework**: `React 19` e `Vite 6+`
*   **Estilização**: `Tailwind CSS v4` usando configuração nativa baseada em CSS e compilação ultra veloz.
*   **State & Cache Management**: `@tanstack/react-query` para sincronização de estado com a API do backend, com invalidação de cache inteligente.
*   **Formulários**: `react-hook-form` acoplado com validações de dados rigorosas do `zod` via `@hookform/resolvers`.
*   **Roteamento**: `react-router-dom v7` para controle de rotas de página única (SPA).
*   **Visualização Gráfica**: `react-apexcharts` para gráficos interativos de fluxo de caixa e alocação de carteira.
*   **Ícones**: `lucide-react` para biblioteca unificada de ícones modernos.

### Infraestrutura & Orquestração
*   **Containers**: `Docker` e `Docker Compose` para isolamento total de serviços.
*   **Orquestrador de Rede**: Script personalizado `run.py` e `./run.sh` para análise ativa e resolução de conflitos de portas.

---

## 📋 Pré-requisitos

Para executar e desenvolver o FreeCash localmente, certifique-se de possuir:

*   **Docker** instalado e configurado (com suporte ao comando `docker compose`).
*   **Python 3.12+** (caso opte pela execução manual fora de containers).
*   **Node.js 20+** e **npm** (para desenvolvimento do Frontend local).

---

## ⚡ Como Rodar o Projeto

O FreeCash oferece duas abordagens para execução: com isolamento completo via Docker (Recomendado) ou localmente de forma manual.

### Opção A: Docker & Port Orchestrator (Recomendado)

O orquestrador gerencia todo o ecossistema. Ele realiza a verificação de portas no host, configura as variáveis necessárias em um arquivo temporário de ambiente `.env.docker` e inicializa o Docker Compose. 

Tanto o script Bash quanto o Python configuram automaticamente o arquivo `.env` a partir do `.env_example` na primeira execução caso você não o possua.

#### 1. Execute o Orquestrador Dinâmico

*   **Método Recomendado (Universal - Zero Dependências de Linguagem)**:
    ```bash
    chmod +x run.sh
    ./run.sh
    ```
*   **Método Alternativo (Requer Python 3 instalado no Host)**:
    ```bash
    python3 run.py
    ```

#### 2. Acesse a Aplicação:
*   **Frontend Client**: [http://localhost:5173](http://localhost:5173) (ou a porta dinamicamente mapeada pelo terminal).
*   **Backend API**: [http://localhost:8000/api/](http://localhost:8000/api/)
*   **PostgreSQL**: Disponível localmente na porta informada pelo terminal (ex: `5433` em caso de conflito na `5432`).

*Para encerrar os containers graciosamente, basta pressionar `Ctrl+C` no terminal.*

---

### Opção B: Localmente (Manual)

#### 1. Configuração do Backend
1.  **Crie e ative o ambiente virtual**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    ```
2.  **Instale os pacotes requeridos**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure as variáveis de ambiente**:
    ```bash
    cp .env_example .env
    ```
    Ajuste as configurações no `.env` conforme necessário para o seu banco de dados PostgreSQL local.
4.  **Execute as migrações de banco e crie o Superusuário**:
    ```bash
    python manage.py migrate
    python manage.py createsuperuser
    ```
5.  **Rode o servidor de desenvolvimento**:
    ```bash
    python manage.py runserver 127.0.0.1:8000
    ```

#### 2. Configuração do Frontend (Vite + React)
Em uma nova janela de terminal, navegue até a pasta `frontend/`:
1.  **Instale as dependências JavaScript**:
    ```bash
    cd frontend
    npm install
    ```
2.  **Inicie o servidor de desenvolvimento**:
    ```bash
    npm run dev
    ```
3.  Acesse [http://localhost:5173](http://localhost:5173). O cliente React se conectará automaticamente com o backend do Django rodando em `localhost:8000`.

---

## 📂 Estrutura do Repositório

O projeto é organizado de forma modular, separando responsabilidades de negócio de forma nítida:

```text
freecash/
├── backend/                    # ECOSSISTEMA BACKEND (DJANGO API)
│   ├── core/                   # Módulo Financeiro Central (Contas, Cartões, Extratos)
│   ├── investimento/           # Módulo de Investimentos (Ativos, ANBIMA, Transações, Cotações)
│   ├── freecash/               # Configurações globais do projeto Django
│   ├── manage.py               # Utilitário de gerenciamento do Django
│   └── requirements.txt        # Dependências Python do backend
│
├── frontend/                   # CLIENTE REATIVO EM REACT 19 (SPA)
│   ├── src/                    # Código fonte do React
│   │   ├── components/         # Componentes UI reutilizáveis (botões, inputs, cards)
│   │   ├── layouts/            # Estrutura base de páginas e Sidebar
│   │   ├── pages/              # Telas da SPA (Dashboard, Investimentos, Extratos)
│   │   ├── services/           # Comunicação com a API (Axios, React Query)
│   │   └── App.jsx             # Ponto de entrada do React
│   ├── tailwind.config.js      # Customização de temas visuais
│   ├── package.json            # Manifesto de dependências e scripts do Frontend
│   └── vite.config.js          # Configurações do Vite
│
├── docker-compose.yml          # Definição e orquestração de containers locais
├── Dockerfile.backend          # Receita de build do ambiente Django
├── Dockerfile.frontend         # Receita de build do ambiente React
├── Dockerfile.postgres         # Customização e inicialização do banco PostgreSQL
└── run.py                      # Dynamic Port Orchestrator local
```

---

## ⚙️ Arquitetura de Dados & Fluxo

### Ciclo de Requisição & Resposta (REST API)

O FreeCash funciona como uma arquitetura desacoplada (Decoupled SPA). A interface React envia requisições assíncronas utilizando **Axios** para a API Django. O Django processa a requisição, interage com o PostgreSQL via ORM e retorna um payload JSON estruturado que atualiza o estado local do React via **React Query**.

```text
+-----------------------+               HTTP REST (JSON)              +-----------------------+
|  Vite + React 19 Client|  =======================================>  |     Django Backend    |
|  (State, React Query) |  <=======================================  |  (DRF Views & Models) |
+-----------------------+           Autenticação JWT Bearer           +-----------------------+
            ||                                                                    ||
            \/                                                                    \/
+-----------------------+                                             +-----------------------+
|   Local Cache / State |                                             |  ActiveRecord / ORM   |
|   (ApexCharts, Zod)   |                                             |   (psycopg3 Driver)   |
+-----------------------+                                             +-----------------------+
                                                                                  ||
                                                                                  \/
                                                                      +-----------------------+
                                                                      | PostgreSQL 16 Database|
                                                                      +-----------------------+
```

---

## 🧪 Testes Automatizados

O backend do FreeCash possui cobertura de testes unitários e de integração para validar a integridade dos cálculos financeiros e as regras de negócio de investimentos.

Para rodar todos os testes unitários do sistema:
```bash
docker compose exec backend python manage.py test
```
Ou rodando localmente fora de containers:
```bash
python manage.py test
```

---

## 🔍 Guia de Troubleshooting (Resolução de Problemas)

### 1. Erro de Porta Ocupada ("Port already in use")
*   **Sintoma**: Ao iniciar o Docker, o banco ou backend falha em subir alegando que a porta `5432` ou `8000` está alocada.
*   **Solução**: Não inicie o projeto utilizando `docker compose up` diretamente. Execute sempre **`./run.sh`** (ou `python3 run.py`). O script detectará a porta ocupada no seu sistema operacional e remapeará os containers para portas livres sem exigir alterações manuais de arquivos.

### 2. Erro de Migrações Pendentes ("Database error - Relation does not exist")
*   **Sintoma**: O Django reporta falha de tabela ausente ou erros de banco de dados ao tentar salvar transações.
*   **Solução**: Se estiver rodando no Docker, os scripts automáticos aplicam as migrações na inicialização. Caso esteja executando manualmente, certifique-se de ativar o ambiente virtual e rodar:
    ```bash
    python manage.py migrate
    ```

### 3. Containers sem Comunicação ("CORS error" ou "Network Error")
*   **Sintoma**: O frontend React abre no navegador, mas as requisições para a API falham e as telas permanecem em loading infinito.
*   **Solução**: Verifique se o backend está ativo. Se o backend estiver rodando em uma porta remapeada pelo orchestrator (ex: `8001`), confirme se a variável `VITE_API_URL` no frontend foi atualizada para apontar para a porta correta. O script orquestrador faz isso automaticamente gerando o arquivo `.env.docker`. Certifique-se de estar rodando os containers via **`./run.sh`** (ou `run.py`) para que a integração de portas seja gerada perfeitamente.
