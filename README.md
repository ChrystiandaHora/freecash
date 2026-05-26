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
*   **Carteira Multi-Ativos**:
    *   **Renda Fixa**: Controle parametrizado contendo Vencimento, Emissor, Indexador (CDI, IPCA, Selic, Pré, IGP-M) e Taxa acordada.
    *   **Renda Variável & Cripto**: Suporte completo a tickers nacionais e internacionais.
*   **Cálculo Automático de Posição**: Controle nativo de **Preço Médio (PM)** e **Quantidade Acumulada** baseado em compras e vendas com compensações dinâmicas de taxas e corretagem.
*   **Gestão de Proventos**: Registro e rastreamento de dividendos, JCP (Juros sobre Capital Próprio) e rendimentos recebidos, com impacto direto na rentabilidade histórica do ativo.
*   **Cotações em Tempo Real**: Integração técnica com APIs de mercado financeiro (Yahoo Finance) para atualizar preços de fechamento diários e calcular a rentabilidade real comparada com o custo médio.

### 3. Dynamic Port Orchestrator (`run.py`)
*   **Zero-Configuration Dev**: Script de orquestração local que analisa automaticamente se as portas padrão (`5432` para PostgreSQL, `8000` para Django, `5173` para React) estão ocupadas por outros processos no Host.
*   **Resolução Dinâmica**: Em caso de conflito, o FreeCash remapeia automaticamente os serviços para as próximas portas disponíveis e gera dinamicamente as variáveis correspondentes no arquivo `.env.docker`, garantindo que os containers e a API se comuniquem perfeitamente sem qualquer intervenção manual do desenvolvedor.

---

## 🛠 Tech Stack

O ecossistema do FreeCash é construído sobre ferramentas modernas e estáveis de desenvolvimento de software:

### Backend (API & Lógica)
*   **Linguagem & Framework**: `Python 3.12+` e `Django 6.0.1`
*   **Banco de Dados**: `PostgreSQL 16` via drivers assíncronos e robustos `psycopg3`
*   **API Engine**: `Django REST Framework (DRF)` para endpoints RESTful de alta performance.
*   **Segurança**: `djangorestframework-simplejwt` para autenticação baseada em tokens JWT.
*   **Integração de Mercado**: `yfinance` para consultas de cotações financeiras globais e nacionais em tempo real.
*   **Processamento de Dados**: `pandas` e `openpyxl` para manipulação, importação e exportação de planilhas.
*   **Engine de PDFs**: `reportlab` e `pdfplumber` para geração e leitura de relatórios financeiros e extratos.
*   **Serviço de Arquivos**: `whitenoise` para servir arquivos estáticos otimizados diretamente pelo container Django.

### Frontend (Interface de Usuário)
*   **Linguagem & Framework**: `React 19` e `Vite 8` (compilação extremamente rápida via ESM).
*   **Estilização**: `Tailwind CSS v4` usando configuração nativa baseada em CSS e compilação ultra veloz.
*   **State & Cache Management**: `@tanstack/react-query` para sincronização de estado com a API do backend, com invalidação de cache inteligente.
*   **Formulários**: `react-hook-form` acoplado com validações de dados rigorosas do `zod` via `@hookform/resolvers`.
*   **Roteamento**: `react-router-dom v7` para controle de rotas de página única (SPA).
*   **Visualização Gráfica**: `apexcharts` e `react-apexcharts` para gráficos interativos de fluxo de caixa e alocação de carteira.
*   **Ícones**: `lucide-react` para biblioteca unificada de ícones modernos.

### Infraestrutura & Orquestração
*   **Containers**: `Docker` e `Docker Compose` para isolamento total de serviços.
*   **Orquestrador de Rede**: Script personalizado `run.py` para análise ativa e resolução de conflitos de portas.

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

O script `run.py` gerencia todo o ecossistema. Ele realiza a verificação de portas no host, configura as variáveis necessárias em um arquivo temporário de ambiente `.env.docker` e inicializa o Docker Compose.

1.  **Configure o Arquivo de Ambiente Base**:
    ```bash
    cp .env_example .env
    ```
2.  **Execute o Orquestrador Dinâmico**:
    ```bash
    python3 run.py
    ```
3.  **Acesse a Aplicação**:
    *   **Frontend Client**: [http://localhost:5173](http://localhost:5173) (ou a porta dinamicamente mapeada pelo terminal).
    *   **Backend API**: [http://localhost:8000/api/](http://localhost:8000/api/)
    *   **PostgreSQL**: Disponível localmente na porta informada pelo terminal (ex: `5433` em caso de conflito na `5432`).

*Para encerrar os containers graciosamente, basta pressionar `Ctrl+C` no terminal onde o `run.py` está em execução.*

---

### Opção B: Desenvolvimento Manual (Sem Docker)

Se preferir rodar o backend e o frontend de forma manual e separada:

#### 1. Banco de Dados
Garanta que possui um servidor **PostgreSQL** ativo localmente. Crie um banco chamado `freecash_db` e configure o arquivo `.env` na raiz do projeto com as credenciais locais:
```env
DB_NAME=freecash_db
DB_USER=seu_usuario
DB_PASS=sua_senha
DB_HOST=localhost
DB_PORT=5432
```

#### 2. Configuração do Backend (Django)
No diretório raiz do projeto:
1.  **Crie e ative um ambiente virtual**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    ```
2.  **Instale os pacotes requeridos**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Execute as migrações de banco e crie o Superusuário**:
    ```bash
    python manage.py migrate
    python manage.py createsuperuser
    ```
4.  **Rode o servidor de desenvolvimento**:
    ```bash
    python manage.py runserver 127.0.0.1:8000
    ```

#### 3. Configuração do Frontend (Vite + React)
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
├── core/                       # MÓDULO FINANCEIRO CENTRAL
│   ├── migrations/             # Histórico de migrações do banco
│   ├── services/               # Lógica de negócio (Importações de Extratos e XLSX)
│   ├── templates/              # Interfaces estáticas e views administrativas
│   ├── models.py               # Modelos de dados (Categoria, Conta, Cartão, Extrato)
│   ├── urls.py                 # Rotas do core e views legadas
│   └── views.py                # Controladores do módulo core
│
├── investimento/               # MÓDULO DE INVESTIMENTOS E CARTEIRA
│   ├── management/commands/    # Scripts (ex: populate_investments para carga inicial)
│   ├── services/               # Motores de busca e APIs de cálculo
│   ├── calculators.py          # Matemática de Preço Médio e quantidade
│   ├── forms.py                # Validação de formulários de investimentos
│   ├── models.py               # Ativos, Classes, Subcategorias ANBIMA, Cotações, Transações
│   ├── signals.py              # Automações orientadas a eventos de banco (Signals)
│   ├── urls.py                 # Rotas de acesso do módulo
│   ├── views.py                # Visualização de investimentos
│   └── views_api.py            # Endpoints REST específicos de investimentos
│
├── freecash/                   # CONFIGURAÇÕES GLOBAIS DO PROJETO DJANGO
│   ├── settings.py             # Configurações globais (DRF, JWT, Banco, CORS)
│   ├── urls.py                 # Orquestrador global de rotas da aplicação
│   └── wsgi.py / asgi.py       # Pontos de entrada para servidores de produção
│
├── frontend/                   # CLIENTE REATIVO EM REACT 19 (SPA)
│   ├── src/
│   │   ├── components/         # Componentes UI reutilizáveis (botões, inputs, cards)
│   │   ├── layouts/            # Estrutura base de páginas e Sidebar
│   │   ├── pages/              # Telas da SPA (Dashboard, Investimentos, Extratos)
│   │   ├── services/           # Comunicação com a API (Instância Axios, React Query)
│   │   └── App.jsx / main.jsx  # Ponto de entrada do React
│   ├── tailwind.config.js      # Customização de temas visuais
│   ├── package.json            # Manifesto de dependências e scripts do Frontend
│   └── vite.config.js          # Configurações do Vite
│
├── docker-compose.yml          # Definição e orquestração de containers locais
├── Dockerfile.backend          # Receita de build do ambiente Django
├── Dockerfile.frontend         # Receita de build do ambiente React (Dev/Prod)
├── Dockerfile.postgres         # Customização e inicialização do banco PostgreSQL
├── requirements.txt            # Dependências Python globais do projeto
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

### Automações Orientadas a Eventos (`investimento/signals.py`)

O FreeCash implementa **Django Signals** para garantir a consistência dos dados do usuário de forma assíncrona e orientada a eventos, eliminando reprocessamentos pesados. O sistema contém dois receivers críticos:

1.  **`criar_classificacao_padrao` (Acionado ao criar Usuário)**:
    Quando um novo registro de usuário é inserido (`post_save` no modelo `User`), o signal inicializa automaticamente a taxonomia completa padrão de investimentos de acordo com o padrão **ANBIMA**:
    *   **Renda Fixa**: Cria automaticamente subcategorias de *Tesouro Selic*, *CDB/RDB*, *LCI/LCA* e *Crédito Privado (CRI/CRA)*.
    *   **Renda Variável**: Inicializa *Ações Brasil*, *BDRs (Internacional)*, *Small Caps* e divisões de *Fundos Imobiliários (FII de Tijolo, FII de Papel, Fiagro)*.
    *   **Criptoativos**: Estrutura as divisões para *Bitcoin*, *Ethereum* e *Altcoins*.
    *   **Multimercado & Cambial**: Configura as moedas (Dólar, Euro) e estratégias macro.

2.  **`atualizar_ativo_apos_transacao` (Acionado por Transações)**:
    Sempre que uma transação de compra, venda ou provento de investimento é criada, atualizada ou excluída (`post_save` e `post_delete` em `Transacao`), este signal é disparado. Ele invoca a função `recalcular_ativo(ativo)` que:
    *   Analisa todo o histórico histórico de compras e vendas do ativo específico daquele usuário.
    *   Recomputa matematicamente a **Quantidade** real acumulada.
    *   Atualiza o **Preço Médio (PM)** de aquisição com precisão de 4 casas decimais.
    *   Grava esses valores como um cache de atributos diretamente na tabela `Ativo`, otimizando a exibição do dashboard sem exigir queries agregadas pesadas em tempo real.

---

## 🗄️ Modelo Relacional de Banco de Dados

Abaixo está o mapeamento detalhado das entidades do banco de dados PostgreSQL estruturado no FreeCash:

```text
==========================================================================================
                                       MÓDULO CORE
==========================================================================================

Categoria (core_categoria)
├── id (BigInt, PK)
├── uuid (UUID, Unique)
├── nome (VarChar(100), Unique por Usuario)
├── tipo (VarChar(1), Choices: 'R' (Receita), 'D' (Despesa), 'I' (Investimento))
├── is_default (Boolean)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

Conta (core_conta)
├── id (BigInt, PK)
├── uuid (UUID, Unique)
├── tipo (VarChar(1), Choices: 'R', 'D', 'I')
├── descricao (VarChar(255))
├── valor (Decimal(12, 2))
├── data_prevista (Date, Indexado)
├── transacao_realizada (Boolean, Indexado)
├── data_realizacao (Date, Null, Indexado)
├── data_compra (Date, Null, Indexado)
├── eh_fatura_cartao (Boolean, Indexado)
├── categoria_id (BigInt, FK -> Categoria, Null)
├── cartao_id (BigInt, FK -> CartaoCredito, Null)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

CartaoCredito (core_cartaocredito)
├── id (BigInt, PK)
├── uuid (UUID, Unique)
├── nome (VarChar(100))
├── bandeira (VarChar(20), Choices: VISA, MASTERCARD, ELO, AMEX, HIPERCARD, etc.)
├── ultimos_digitos (VarChar(4))
├── limite (Decimal(12, 2), Null)
├── dia_fechamento (Integer)
├── dia_vencimento (Integer)
├── ativo (Boolean)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

==========================================================================================
                                   MÓDULO INVESTIMENTO
==========================================================================================

ClasseAtivo (investimento_classeativo)
├── id (BigInt, PK)
├── nome (VarChar(60), Unique por Usuario)
├── ativa (Boolean)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

CategoriaAtivo (investimento_categoriaativo)
├── id (BigInt, PK)
├── classe_id (BigInt, FK -> ClasseAtivo)
├── nome (VarChar(60), Unique por Usuario/Classe)
├── ativa (Boolean)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

SubcategoriaAtivo (investimento_subcategoriaativo)
├── id (BigInt, PK)
├── categoria_id (BigInt, FK -> CategoriaAtivo)
├── nome (VarChar(60), Unique por Usuario/Categoria)
├── ativa (Boolean)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

Ativo (investimento_ativo)
├── id (BigInt, PK)
├── ticker (VarChar(20), Unique por Usuario)
├── nome (VarChar(120))
├── subcategoria_id (BigInt, FK -> SubcategoriaAtivo, Null)
├── data_vencimento (Date, Null)
├── emissor (VarChar(100))
├── indexador (VarChar(10), Choices: CDI, IPCA, SELIC, PRE, IGPM, etc.)
├── taxa (Decimal(9, 4))
├── moeda (VarChar(10), Default: 'BRL')
├── ativo (Boolean)
├── meta_porcentagem (Decimal(5, 2))
├── quantidade (Decimal(19, 8), Cache Calculado)
├── preco_medio (Decimal(19, 4), Cache Calculado)
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]

Transacao (investimento_transacao)
├── id (BigInt, PK)
├── ativo_id (BigInt, FK -> Ativo)
├── tipo (VarChar(1), Choices: 'C' (Compra), 'V' (Venda), 'D' (Provento))
├── data (Date)
├── quantidade (Decimal(19, 8))
├── preco_unitario (Decimal(19, 4))
├── taxas (Decimal(12, 2))
├── valor_total (Decimal(19, 2))
├── usuario_id (BigInt, FK -> auth_user)
└── [Auditoria: criada_em, atualizada_em]
```

---

## 🔑 Variáveis de Ambiente

O FreeCash utiliza arquivos `.env` para segurança de credenciais sensíveis e portabilidade de portas locais.

### Configurações do Banco de Dados
*   `DB_NAME`: Nome do banco de dados relacional (Ex: `freecash_db`).
*   `DB_USER`: Usuário administrativo do PostgreSQL (Ex: `freecash_user`).
*   `DB_PASS`: Senha do usuário do banco (Ex: `freecash_pass`).
*   `DB_HOST`: Host de conexão do banco (`postgres` ao rodar em containers Docker, `localhost` na execução manual).
*   `DB_PORT`: Porta interna do PostgreSQL no container (Padrão: `5432`).

### Configurações de Rede (Orquestradas automaticamente pelo `run.py`)
*   `POSTGRES_PORT`: Porta mapeada do PostgreSQL no Host Host (Ex: `5433` em caso de conflitos locais).
*   `BACKEND_PORT`: Porta exposta do servidor Django Backend (Padrão: `8000`).
*   `FRONTEND_PORT`: Porta exposta do servidor React Vite Frontend (Padrão: `5173`).
*   `VITE_API_URL`: URL base de comunicação HTTP que o cliente Vite utilizará (Ex: `http://localhost:8000`).

---

## 🛠️ Comandos e Scripts Úteis

O projeto possui comandos consolidados para operações cotidianas:

| Comando | Descrição |
| :--- | :--- |
| `python3 run.py` | Executa o port-scanner, constrói e inicializa todos os containers Docker. |
| `python manage.py makemigrations` | Gera novos arquivos de migrações com base nas alterações dos modelos. |
| `python manage.py migrate` | Aplica migrações pendentes ao banco de dados PostgreSQL. |
| `python manage.py createsuperuser` | Cria um usuário administrador para acessar o painel Django Admin (`/admin`). |
| `python manage.py populate_investments` | Comando customizado para popular a taxonomia padrão de investimentos retroativamente. |
| `python manage.py shell` | Abre o terminal interativo do Python com o contexto do Django inicializado. |
| `python manage.py test` | Executa a suite completa de testes automatizados do backend. |
| `npm run build:css` (raiz) | Compila e minifica as classes do Tailwind CSS do core de forma manual. |

---

## 🧪 Testes Automatizados

O backend do FreeCash possui cobertura de testes unitários e de integração para validar a integridade dos cálculos financeiros e as regras de negócio de investimentos.

Para rodar todos os testes unitários do sistema:
```bash
python manage.py test core investimento
```

Se desejar executar os testes de um módulo específico com riqueza de detalhes:
```bash
python manage.py test investimento.tests
```

---

## 🔍 Guia de Troubleshooting (Resolução de Problemas)

### 1. Erro de Porta Ocupada ("Port already in use")
*   **Sintoma**: Ao iniciar o Docker, o banco ou backend falha em subir alegando que a porta `5432` ou `8000` está alocada.
*   **Solução**: Não inicie o projeto utilizando `docker compose up` diretamente. Execute sempre **`python3 run.py`**. O script detectará a porta ocupada no seu sistema operacional e remapeará os containers para portas livres sem exigir alterações manuais de arquivos.

### 2. Erro de Migrações Pendentes ("Database error - Relation does not exist")
*   **Sintoma**: O Django reporta falha de tabela ausente ou erros de banco de dados ao tentar salvar transações.
*   **Solução**: Se estiver rodando no Docker, os scripts automáticos aplicam as migrações na inicialização. Caso esteja executando manualmente, certifique-se de ativar o ambiente virtual e rodar:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

### 3. Cotações Financeiras Desatualizadas
*   **Sintoma**: Ativos de renda variável são exibidos no Dashboard de Investimento com a rentabilidade zerada ou com fallback de preço médio.
*   **Solução**: O FreeCash depende do ticker correto cadastrado no ativo (ex: `PETR4.SA` para ações da Petrobras no mercado brasileiro ou `BTC-USD` para Bitcoin). Verifique se o ticker inserido está em conformidade com os tickers suportados pelo Yahoo Finance (`yfinance`).

### 4. Containers sem Comunicação ("CORS error" ou "Network Error")
*   **Sintoma**: O frontend React abre no navegador, mas as requisições para a API falham e as telas permanecem em loading infinito.
*   **Solução**: Verifique se o backend está ativo. Se o backend estiver rodando em uma porta remapeada pelo orchestrator (ex: `8001`), confirme se a variável `VITE_API_URL` no frontend foi atualizada para apontar para a porta correta. O script `run.py` faz isso automaticamente gerando o arquivo `.env.docker`. Certifique-se de estar rodando os containers via `run.py` para que a integração de portas seja gerada perfeitamente.
