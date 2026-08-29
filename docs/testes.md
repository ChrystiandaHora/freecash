# Testes

Como rodar a suíte do FreeCash na sua máquina, o que cada convenção do projeto
exige e o que ainda não está coberto.

Hoje são **425 testes de backend** e a cobertura geral é de **74%**. Eles rodam
localmente pelos comandos abaixo e automaticamente a cada pull request para
`main` — ver [Rodando na esteira do GitHub](#rodando-na-esteira-do-github) no fim,
inclusive para o custo (zero, neste repositório) e para como desligar.

---

## O que o projeto usa

`unittest` do Django — `APITestCase` do DRF para endpoints, `TestCase` para
serviços e modelos. **Não há pytest**, apesar de existir um binário `py.test` no
virtualenv: nenhum teste do repositório usa a API do pytest, e `manage.py test` é
o único runner suportado.

Os testes precisam de **PostgreSQL**. SQLite não serve: a migration
`core/0002_email_unico_case_insensitive` cria um índice único parcial sobre
`LOWER(email)`, sintaxe que só o Postgres entende.

---

## Rodando com Docker (caminho recomendado)

Com os contêineres de pé (`./run.sh` ou `docker compose up -d`):

```bash
docker compose exec backend python manage.py test
```

O Django cria um banco `test_<DB_NAME>` separado e o destrói no fim — o banco de
desenvolvimento não é tocado.

## Rodando direto na máquina

Precisa de um Postgres acessível. Se você tem um instalado via Homebrew, o
caminho mais curto é apontar as variáveis do banco para ele, sem mexer no `.env`
(que aponta para o host `postgres`, o nome do serviço dentro do Docker):

```bash
cd backend
DB_HOST=localhost DB_PORT=5432 DB_USER="$(whoami)" DB_PASS="" DB_NAME=postgres \
DJANGO_DEBUG=True python manage.py test
```

Duas coisas valem saber:

- O usuário informado precisa poder **criar bancos** — é o que o Django faz para
  montar o `test_*`. Um usuário comum sem essa permissão falha no primeiro passo.
- `DB_NAME` aqui é só o banco usado para abrir a conexão inicial; o banco de
  testes é criado com nome próprio a partir dele.

Se preferir usar o Postgres do Docker sem entrar no contêiner do backend, suba só
o banco (`docker compose up -d postgres`) e use `DB_HOST=localhost` com as
credenciais do `.env`.

---

## Rodando um subconjunto

Quanto mais estreito o alvo, mais rápido o ciclo. Todos os exemplos aceitam os
mesmos prefixos:

```bash
python manage.py test core.tests                      # todo o app core
python manage.py test investimento.tests              # todo o app investimento
python manage.py test core.tests.test_auth_backends   # um arquivo
python manage.py test core.tests.test_health.HealthCheckAPITests            # uma classe
python manage.py test core.tests.test_health.HealthCheckAPITests.test_responde_ok_sem_autenticacao
```

## Flags que valem a pena

| Flag | Para quê |
|---|---|
| `--parallel` | Distribui por núcleos. A suíte inteira cai de ~75s para ~25s. |
| `--keepdb` | Reaproveita o banco de testes entre execuções, poupando o setup. Invalide (rode sem a flag) sempre que criar migration nova. |
| `--failfast` | Para no primeiro erro. Bom quando você já sabe que quebrou algo. |
| `-v 2` | Imprime o nome de cada teste. Útil para descobrir qual está lento ou travado. |
| `--debug-sql` | Mostra o SQL das consultas dos testes que falharam. |

---

## Cobertura

`coverage` está em `backend/requirements-dev.txt`, fora da imagem de produção:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

A configuração vive em [`backend/.coveragerc`](../backend/.coveragerc). Ela usa
`parallel = true` para conseguir medir os subprocessos de `--parallel`, e isso
torna o `combine` obrigatório antes do relatório:

```bash
cd backend
coverage erase
coverage run manage.py test
coverage combine
coverage report -m          # tabela no terminal, com as linhas não cobertas
coverage html               # relatório navegável em backend/htmlcov/index.html
```

Migrations, os próprios testes, `settings.py` e o seed de dados de demonstração
ficam fora da medição: são código gerado ou executado uma vez, e medi-los só
inflaria o número sem dizer nada sobre qualidade.

---

## Convenções que os testes deste projeto exigem

Quatro pontos específicos do FreeCash. Ignorar os três primeiros produz teste
intermitente — que passa na sua máquina e falha na próxima execução.

### 1. E-mail: desligue o envio assíncrono

`email_service` despacha em `threading.Thread` quando `EMAIL_ASYNC` está ligado
(o padrão). Com thread, `mail.outbox` é lido antes de o envio acontecer, e o
teste passa ou falha conforme o escalonamento do sistema operacional.

```python
@override_settings(EMAIL_ASYNC=False)
class MeuTeste(APITestCase):
    ...
```

### 2. E-mail: force os callbacks de commit

O envio é agendado com `transaction.on_commit`, para que nada saia se a
transação der rollback. Dentro de um `TestCase`, a transação **nunca** commita —
ela é revertida no fim de cada teste. O callback só roda se você pedir:

```python
with self.captureOnCommitCallbacks(execute=True):
    resposta = self.client.post("/api/register/", dados, format="json")

self.assertEqual(len(mail.outbox), 1)
```

Sem isso, `mail.outbox` fica vazio e o teste conclui, errado, que o e-mail não
foi enviado. A referência completa está em [autenticacao.md](autenticacao.md).

### 3. Throttle: limpe o cache entre testes

O rate limit de `/api/token/` e `/api/register/` usa o cache `throttle`, que é um
`DatabaseCache`. Ele **persiste entre testes** dentro da mesma classe: o segundo
teste que faz login começa com as tentativas do primeiro já contabilizadas e
recebe 429 sem motivo aparente.

```python
from django.core.cache import caches

def setUp(self):
    caches["throttle"].clear()
```

A tabela desse cache é criada por `manage.py createcachetable`, não por
migration. Nos **testes** você não precisa se preocupar: o Django cria as tabelas
de cache junto com o banco de testes. Já para rodar a **aplicação** localmente
fora do Docker, execute o comando uma vez — sem a tabela, todo endpoint com
throttle devolve erro 500. No Docker, o `entrypoint.sh` cuida disso a cada boot.

### 4. Isolamento por usuário

Quase todo modelo do projeto é escopado por usuário. Um teste que cria dados sem
`usuario=` ou que consulta sem filtrar passa a depender do que outros testes
deixaram no banco. O padrão do repositório é criar duas contas e verificar que
uma não alcança os dados da outra — ver `test_isolamento_cotacoes.py` e
`test_api_admin.py`.

---

## Testes do frontend

Vitest, com muito menos cobertura que o backend (hoje só `lib/`):

```bash
cd frontend
npm run test        # execução única
npm run test:watch  # re-roda ao salvar
npm run lint        # ESLint
```

**Sobre o `npm run lint`:** ele acusa hoje 24 erros que já existiam antes de o CI
ser configurado — quase todos `react-hooks/set-state-in-effect` e
`react-refresh/only-export-components`, concentrados nas telas de investimento
(`AtivosClasses.jsx`, `PipelineKanban.jsx` e formulários). Por isso o passo de
lint no CI está marcado como `continue-on-error`: ele reporta, mas não reprova o
pull request. Zerar essa lista é trabalho próprio; quando acontecer, basta
remover essa linha do workflow para que qualquer regressão volte a reprovar.

---

## O que ainda não está coberto

Mapa honesto do que falta, em ordem de risco:

| Módulo | Cobertura | Por que importa |
|---|---|---|
| `core/services/extrato_parser.py` | 5% | Faz o parse de PDF de extrato e fatura. É o código que mais lida com entrada imprevisível. |
| `investimento/services/cvm_service.py` | 12% | Baixa e interpreta os informes diários da CVM. Depende de I/O externo, então precisa de teste com resposta gravada. |
| `investimento/services/tradingview_screener.py` | 38% | Também I/O externo. |
| `investimento/views_api.py` | 44% | Só `AtivoViewSet` é testado; os outros ViewSets não. |
| `investimento/services/carteira_historico_service.py` | 46% | Cálculo de histórico de carteira. |
| `core/management/commands/categorizar_gastos_cartao.py` | 0% | Recategoriza gastos em lote — altera dados existentes sem rede de proteção. |

O app `investimento` inteiro tem 14 testes contra ~410 do `core`. É a lacuna
maior, e o obstáculo real é que os três serviços mais descobertos fazem chamadas
de rede: cobri-los exige gravar respostas de exemplo (fixtures), não apenas
escrever asserções.

---

## Rodando na esteira do GitHub

Existe um workflow em [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
que roda backend e frontend a cada pull request para `main`, e também sob demanda
(aba **Actions** → **CI** → *Run workflow*).

Ele faz três coisas por execução: confere se existe migration não commitada
(`makemigrations --check`), roda os 425 testes de backend contra um Postgres 16 de
verdade, e roda os testes do frontend. O lint aparece no log sem reprovar, pelo
motivo explicado acima.

**Custo:** o repositório é público, então o GitHub Actions é **gratuito e sem
limite de minutos** nos runners padrão. Não há como essa configuração gerar
cobrança. Se o repositório algum dia virar privado, o plano Free dá 2.000
minutos/mês — a suíte gasta cerca de 3 minutos por execução, o que caberia com
folga, mas o custo deixa de ser zero.

### Fazer o CI bloquear o merge

O workflow rodando não impede merge nenhum: ele apenas reporta. Para o botão de
merge travar quando os testes falham, é preciso habilitar a proteção de branch,
no site do GitHub:

1. **Settings** → **Branches** → **Add branch ruleset** (ou *Add rule*).
2. Em *Branch name pattern*, use `main`.
3. Marque **Require status checks to pass before merging**.
4. Procure e selecione `backend-tests` e `frontend-tests`.
5. Salve.

Os checks só aparecem nessa lista **depois** de terem rodado ao menos uma vez —
então abra um pull request de teste antes de configurar a regra.

### Desligar o CI

Se quiser parar as execuções automáticas sem apagar o arquivo, remova o bloco
`pull_request:` dos triggers do workflow. O `workflow_dispatch` sozinho mantém
apenas a execução manual.
