# FreeCash

Aplicação Django para controle financeiro pessoal. O projeto oferece um painel simples para acompanhar receitas, despesas e saldo do mês, além de ferramentas para importar dados históricos provenientes de planilhas legadas e exportar um backup completo em Excel no momento do logout.

## Tecnologias e dependências principais
- Python 3.11+
- Django 4.2.27
- PostgreSQL 13+ (configurado em `freecash/settings.py`)
- Pandas (importação de planilhas legadas)
- OpenPyXL (geração de planilhas de backup)
- `psycopg2-binary` ou equivalente para conectar no PostgreSQL

## Funcionalidades em destaque
- **Dashboard financeiro** (`/dashboard/`): mostra totais de receitas e despesas do mês atual, saldo consolidado, últimas transações e um resumo dos três últimos meses (`core/views/dashboard.py` + `core/templates/dashboard.html`).
- **Modelagem financeira** (`core/models.py`): categorias por tipo (receita/despesa), formas de pagamento, transações detalhadas, resumos mensais herdados de planilhas e configurações do usuário.
- **Importação de planilhas legadas** (`core/services/import_planilha.py`): converte abas com anos (ex.: 2024, 2025) para registros de resumo e transações artificiais, preservando a origem (linha/mês) nos campos `origem_*`.
- **Exportação automatizada** (`core/services/exportar_planilha.py` + `core/views/logout_export.py`): gera um XLSX com transações, categorias, formas de pagamento, resumos e configurações, enviado como download ao fazer logout.
- **Autenticação padrão Django**: todas as rotas protegidas usam `login_required`, e o `LOGIN_REDIRECT_URL` foi definido para o dashboard.

## Estrutura do projeto
```text
freecash/
├── core/
│   ├── models.py            # Modelos financeiros (Categorias, Transações, etc.)
│   ├── services/            # Importação/exportação de planilhas
│   ├── templates/           # Dashboard HTML
│   └── views/               # Dashboard e logout com exportação
├── freecash/                # Configurações e roteamento do Django
└── manage.py
```

## Pré-requisitos
1. Python 3.11 ou superior instalado e disponível no PATH.
2. PostgreSQL em execução local com um banco criado (`freecash_db`) e usuário com permissão (padrão: `postgres/postgres`).
3. Virtualenv recomendado para isolar dependências.

## Configuração e execução local
```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install django==4.2.27 pandas openpyxl psycopg2-binary

# Ajuste DATABASES se necessário em freecash/settings.py
python manage.py migrate
python manage.py createsuperuser    # cria credenciais para acessar /admin e o dashboard
python manage.py runserver
```
Depois de logado, acesse `http://127.0.0.1:8000/dashboard/` para visualizar os indicadores financeiros.

## Importação de planilhas legadas
O serviço `importar_planilha_excel` lê planilhas em que cada aba representa um ano e as linhas "Receita", "Outras Receitas" e "Gastos" contêm os valores mensais. Para importar:
```bash
python manage.py shell
```
```python
from core.services.import_planilha import importar_planilha_excel
from django.contrib.auth import get_user_model
usuario = get_user_model().objects.get(email="seu-email@example.com")
importar_planilha_excel("/caminho/planilha.xlsx", usuario)
exit()
```
As transações criadas são marcadas com `is_legacy=True` e campos `origem_*`, facilitando filtros e exclusões futuras.

## Exportação e backup
Ao acessar `/logout/`, a view `LogoutComExportacaoView` gera automaticamente um XLSX com:
1. Transações ordenadas cronologicamente;
2. Categorias, formas de pagamento e resumos mensais;
3. Configurações do usuário.
O arquivo já vem nomeado com timestamp e o campo `ConfigUsuario.ultimo_export_em` é atualizado para auditoria.

## Testes
Ainda não há testes automatizados implementados, mas o comando padrão está pronto:
```bash
python manage.py test core
```
Priorize a criação de testes para serviços de importação/exportação e para a view do dashboard.

## Próximos passos sugeridos
1. Criar um `requirements.txt` ou `pyproject.toml` para padronizar dependências.
2. Adicionar rotas CRUD para categorias, formas de pagamento e transações (ou expor via Django Admin).
3. Substituir a configuração de banco hard-coded por variáveis de ambiente.
4. Criar testes unitários para garantir que importações/exportações mantenham integridade dos dados.
