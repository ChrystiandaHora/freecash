# FreeCash

Aplicação web em Django para controle financeiro pessoal com onboarding direto na landing page, painel analítico responsivo e ferramentas de importação/exportação em planilhas Excel.

## Visão geral do produto
- **Onboarding rápido** (`core/views/lading.py` + `core/templates/ladingPage.html`): cria usuário e provisiona categorias/forma de pagamento padrão via `core/services/criar_usuario.py`.
- **Dashboard analítico** (`core/views/dashboard.py`): mostra receitas/despesas/saldo do período, variação vs. mês anterior, séries diárias e de 6 meses, breakdown de despesas por categoria, contas atrasadas/pendentes e últimas transações.
- **Contas a pagar** (`core/views/contas.py` + `core/templates/contas.html`): cadastro, listagem pagas/pendentes com paginação e ação de "marcar como paga" (registra realização e data).
- **Receitas e transações** (`core/views/receitas.py`, `core/views/transacoes.py`): filtros por data, categoria e forma de pagamento, paginação e criação rápida de receitas.
- **Importação/exportação unificada** (`core/views/importar.py`, `core/views/exportar.py`, `core/services/importar_unificado.py`, `core/services/exportar_planilha.py`): exporta backup completo (metadados, contas, categorias, formas de pagamento, resumo mensal, configurações) e importa tanto backups FreeCash quanto planilhas legadas por ano; logs ficam em `LogImportacao`.

## Stack e dependências
- Python 3.11+, Django 4.2.27
- PostgreSQL (configurado em `freecash/settings.py`)
- Pandas, OpenPyXL, xlrd para importação/exportação
- python-dotenv para carregar `.env`
- Tailwind CDN + Chart.js nos templates

Versões exatas em `requirements.txt`.

## Estrutura do projeto
```text
freecash/
├── core/
│   ├── models.py              # Categorias, formas, contas (transações/contas a pagar), resumos, configs e logs
│   ├── services/              # Importação/exportação e criação de usuário padrão
│   ├── templates/             # Landing, dashboard, contas, transações, import/export etc.
│   └── views/                 # Views de cada fluxo (CBVs)
├── freecash/                  # Configurações e roteamento do Django
├── docker-compose.yml         # Stack Docker (web + PostgreSQL)
├── Dockerfile.web / Dockerfile.postgres
├── requirements.txt
└── manage.py
```

## Variáveis de ambiente
Use o modelo e ajuste para o seu ambiente:
```bash
cp .env_example .env
```
Campos principais: `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT` (quando rodar local sem Docker, troque `DB_HOST` para `localhost`).

## Rodando localmente (sem Docker)
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env_example .env                 # ajuste as credenciais do seu PostgreSQL local
python manage.py migrate
python manage.py createsuperuser     # opcional, para acessar /admin
python manage.py runserver
```
Acesse `http://127.0.0.1:8000/`. A landing page permite registrar-se; o usuário criado já recebe categorias e formas de pagamento padrão.

## Rodando com Docker Compose
```bash
cp .env_example .env                 # personalize usuário/senha do banco
docker compose up --build
```
O serviço `web` executa migrações e sobe em `http://localhost:8000`, usando o banco `postgres` definido no compose. Os dados persistem no volume `postgres_data`.

## Importação e exportação de dados
- **Exportar:** autenticado, acesse `/exportar/` ou envie `POST /exportar/`. O backup XLSX inclui metadados, contas, categorias, formas de pagamento, resumos mensais e configurações; `ConfigUsuario.ultimo_export_em` é atualizado.
- **Importar:** em `/importar/`, envie um `.xlsx` (backup FreeCash ou planilha legado com abas de ano e linhas "Receita/Outras Receitas/Gastos"); cada tentativa gera um registro em `LogImportacao`, exibido na tela.
- **Uso via shell (opcional):**
  ```bash
  python manage.py shell
  ```
  ```python
  from core.services.importar_unificado import importar_planilha_unificada
  from django.contrib.auth import get_user_model
  usuario = get_user_model().objects.get(username="seu_usuario")
  importar_planilha_unificada("/caminho/arquivo.xlsx", usuario, sobrescrever=True)
  exit()
  ```

## Comandos úteis
- Rodar testes: `python manage.py test core`
- Criar superusuário: `python manage.py createsuperuser`

## Notas rápidas
- A config do usuário (`ConfigUsuario`) é atualizada via signals quando dados financeiros mudam.
- O fuso horário padrão é `America/Sao_Paulo` (`freecash/settings.py`).
