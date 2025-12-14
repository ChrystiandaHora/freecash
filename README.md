# FreeCash

FreeCash é uma aplicação em Django para controle financeiro pessoal. O sistema traz onboarding direto na landing page, painel com gráficos alimentados por dados reais, fluxo de contas a pagar e ferramentas de importação/exportação em planilhas Excel.

## Principais recursos
- **Landing page com login e registro** (`core/views/lading.py` + `core/templates/ladingPage.html`): cria usuários e automaticamente provisiona configurações/categorias padrão via `core/services/criar_usuario.py`.
- **Dashboard financeiro responsivo** (`core/views/dashboard.py`): consolida receitas, despesas e saldo do mês, últimas transações, resumo trimestral e gráficos (doughnut + barras) com Chart.js.
- **Gestão de contas a pagar** (`core/views/contas.py`): cadastro, listagem de pendentes/pagas e botão para "marcar como paga", que gera a transação de despesa correspondente.
- **Listagem e filtros de transações** (`core/views/transacoes.py`): filtros por ano, mês, tipo, categoria e forma de pagamento com resultados ordenados por data.
- **Importação unificada** (`core/views/importar.py` + `core/services/importar_unificado.py`): aceita backups modernos (`core/services/exportar_planilha.py`) ou planilhas legadas por ano, salvando logs em `LogImportacao`.
- **Exportação/backup completo** (`core/services/exportar_planilha.py`): gera XLSX com transações, categorias, formas de pagamento, resumos mensais, contas a pagar e configurações do usuário.

## Stack e dependências
- Python 3.11 e Django 4.2
- PostgreSQL (configurado em `freecash/settings.py`)
- `pandas`, `openpyxl`, `xlrd` para importação/exportação
- `python-dotenv` para carregar o `.env`
- Tailwind CDN e Chart.js nos templates

As versões exatas estão em `requirements.txt`.

## Estrutura
```text
freecash/
├── core/
│   ├── models.py             # Categorias, transações, contas a pagar, resumos, configs e logs
│   ├── services/             # Importar/exportar planilhas e criação de usuário padrão
│   ├── templates/            # Landing page, dashboard e telas internas
│   └── views/                # Views baseadas em classe para cada fluxo
├── freecash/                 # Configurações e roteamento do Django
├── docker-compose.yml        # Ambiente Docker (web + PostgreSQL)
├── Dockerfile.web / .postgres
├── requirements.txt
└── manage.py
```

## Variáveis de ambiente
Use o modelo e adapte conforme o ambiente:
```bash
cp .env_example .env
```
Campos disponíveis:

| Variável | Função |
| --- | --- |
| `DB_NAME`, `DB_USER`, `DB_PASS` | Credenciais do PostgreSQL |
| `DB_HOST`, `DB_PORT` | Host/porta (ex.: `postgres` quando usa Docker) |

O `python-dotenv` é carregado no `settings.py`, logo `.env` na raiz já é lido.

## Executando localmente (sem Docker)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env_example .env               # ajuste valores para seu banco
python manage.py migrate
python manage.py runserver
```
Acesse `http://127.0.0.1:8000/`. A landing page permite criar um usuário (que já recebe categorias padrão) ou fazer login. Para acessar o Django Admin crie um superusuário com `python manage.py createsuperuser`.

## Executando com Docker Compose
```bash
cp .env_example .env               # personalize usuário/senha do banco
docker compose up --build
```
O container `web` executa `makemigrations`, `migrate` e sobe o servidor em `http://localhost:8000`, enquanto `postgres` mantém os dados em `postgres_data`.

## Importação e exportação
- **Exportar:** acesse `/exportar/` autenticado ou envie `POST /exportar/`. O arquivo recebe timestamp no nome e atualiza `ConfigUsuario.ultimo_export_em`.
- **Importar:** em `/importar/` faça upload de um `.xlsx`. O serviço `importar_planilha_unificada` detecta se o arquivo é um backup moderno (abas `transacoes`, `categorias`, etc.) ou planilha legado (abas nomeadas pelo ano com linhas "Receita/Outras Receitas/Gastos"). Toda tentativa gera registro em `LogImportacao`.
- **Uso direto via shell:** também é possível chamar `importar_backup_excel`, `importar_planilha_excel` ou `importar_planilha_unificada` pelo `python manage.py shell`.

## Testes
Ainda não há cobertura total, mas o comando já está disponível:
```bash
python manage.py test core
```
Priorize cenários para importação/exportação e fluxos críticos de contas a pagar.

## Próximos passos sugeridos
1. Completar o CRUD de formas de pagamento (atualmente a página exibe apenas o layout).
2. Persistir e exibir o histórico de importações na tela `importar.html`.
3. Adicionar paginação/estado selecionado aos filtros de transações.
4. Automatizar a exportação durante o logout (a view `LogoutView` hoje apenas redireciona para a landing page).
