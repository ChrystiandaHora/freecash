# Proposta: qualidade e segurança a partir do material de curso

Plano de mudanças para o freecash, derivado das oito apostilas em `docs/*.pdf` (teste,
revisão e análise estática, segurança, ML). Cada item diz **o que mudar**, **de onde vem
no material**, **onde fica no código** e **como saber que ficou pronto**. Levantamento
feito em 2026-11-02 contra o `main` em `b71d02f`.

---

## Ponto de partida (medido, não estimado)

| O quê | Situação |
|---|---|
| Testes do backend | 649 testes, todos passando, ~2 min (`manage.py test` no container) |
| Cobertura do backend | **82% no total** (branch coverage ligada no `.coveragerc`) |
| Arquivos pior cobertos | `extrato_parser.py` **5%**, `categorizar_gastos_cartao.py` 0%, `cvm_service.py` 12%, `tradingview_screener.py` 35%, `dashboard_helper.py` 68%, `views/api.py` 69% |
| Testes do frontend | 16 arquivos de Vitest, todos de `lib/` ou `config/`. Nenhum componente testado |
| E2E | Nenhum |
| CI | Nenhum workflow em `.github/` |
| Linter Python | Nenhum. O frontend tem ESLint com `jsx-a11y` |
| Dependências npm | `npm audit --omit=dev`: **3 de severidade alta** (`follow-redirects`, `source-map-js`, `zod`), todas com correção |
| Dependências Python | Sem auditoria (`pip-audit` não está instalado) |
| `check --deploy` | Avisos só porque o teste rodou com `DEBUG=True`. O bloco `if not DEBUG` do `settings.py` cobre HSTS, SSL e cookies |
| Cabeçalho CSP | Ausente no Caddy, no nginx e no `index.html` |
| `docs/testes.md` | Citado em `requirements-dev.txt` e `.coveragerc`, mas **não existe** |

O que já está bem e não entra no plano:
- JWT de curta duração com rotação e blacklist.
- Cookie `HttpOnly` com path restrito.
- Throttle nas rotas de autenticação e de backup.
- Política de senha NIST.
- Validação de boot em produção.
- Teto de tamanho e checagem do tamanho declarado no import do ZIP.
- Isolamento por usuário testado em 21 arquivos.

---

## Fase 1: achados concretos de segurança

São pequenos, localizados e têm teste óbvio. É por aqui que convém começar.

### 1.1 Uploads sem limite de custo

Este é o caso de "inanição de recursos" e de "dados inesperados que derrubam o
componente" descrito em *Cultura de segurança*, e o DoS do STRIDE.

- **Onde:** `core/views/ferramentas_api.py`, em `FerramentasImportarAPIView`, `FerramentasImportarExtratoAPIView` e `FerramentasConciliacaoUploadAPIView`.
- **Problema:**
  - As três aceitam upload sem `throttle_scope`. A exportação de backup tem throttle, a importação não.
  - `processar_pdf` com `banco="generico"` pode abrir o mesmo PDF **três vezes** em cascata e percorre `pdf.pages` sem teto de páginas.
  - O único limite de tamanho é o `client_max_body_size 20M` do nginx, que não vale em desenvolvimento nem num deploy sem esse nginx.
  - Nenhuma das duas rotas de PDF confere se o arquivo é PDF.
  - `FerramentasImportarExtratoAPIView` não valida `banco`; a de conciliação valida.
- **Mudança:**
  - Criar o escopo `importacao` (por exemplo `20/hour`) nas três views.
  - Conferir a assinatura `%PDF-` nos primeiros bytes.
  - Definir um teto de páginas (`MAX_PAGINAS_EXTRATO`) e um teto de bytes no próprio Django (`DATA_UPLOAD_MAX_MEMORY_SIZE` e `FILE_UPLOAD_MAX_MEMORY_SIZE`, ou checar `arquivo.size` na view).
  - Validar `banco` na rota de fatura, como já faz a de conciliação.
- **Teste:**
  - Arquivo `.pdf` cujo conteúdo é texto devolve 400.
  - PDF acima do teto de páginas devolve 400.
  - A 21ª chamada na hora devolve 429.
  - `banco=xpto` devolve 400.

### 1.2 Mensagem de exceção crua devolvida ao cliente

É o *Information Disclosure* do STRIDE. Também é o "nunca engolir erro em silêncio"
das regras do projeto.

- **Onde:** `ferramentas_api.py:69`, `:185` e `:282`. As três fazem `except Exception as e` e devolvem `f'...: {str(e)}'`, **sem log**.
- **Problema:**
  - Um erro de banco, de caminho do arquivo temporário ou do pdfplumber chega inteiro ao navegador.
  - No servidor não fica registro, então a falha só é vista por quem a recebeu.
- **Mudança:**
  - `ValueError` continua com a mensagem própria. O `import_service` já usa esse tipo para mensagens amigáveis.
  - Qualquer outra exceção passa por `logger.exception(...)` e devolve uma mensagem genérica.
- **Teste:** com `processar_pdf` simulado para levantar `RuntimeError("segredo")`, a resposta não contém `segredo` e o log contém.

### 1.3 Importação de fatura não atômica

É a confiabilidade da ISO 25010.

- **Onde:** o laço `Conta.objects.create` em `FerramentasImportarExtratoAPIView`.
- **Problema:** um erro na linha 30 deixa as 29 anteriores gravadas. Reenviar o arquivo resolve por causa do `exists()`, mas o estado intermediário é visível.
- **Mudança:** envolver o laço em `transaction.atomic()`.
- **Teste:** com uma falha forçada na N-ésima linha, a contagem de `Conta` fica igual à de antes.

### 1.4 Dependências: inventário e monitoramento

Vem da prática 7 do SDL (componentes de terceiros: inventário, plano de resposta e
monitoramento contínuo) e do uso de CVE para dependências (*Cultura de segurança*).

- **Mudança:**
  - Aplicar `npm audit fix` para os 3 avisos altos e conferir a build.
  - Adicionar `pip-audit` ao `requirements-dev.txt`.
  - Criar `.github/dependabot.yml` para `pip`, `npm` e `docker`, com frequência semanal.
- **Prazo por severidade:** é o "bug bar" do SDL, numa versão de uma pessoa só. Crítica corrigida em até 7 dias, alta em até 30, o resto na próxima rodada. Registrar isso em `docs/seguranca.md`.

### 1.5 Content-Security-Policy

É defesa em profundidade contra XSS (OWASP Top 10, A03).

- **Onde:** `deploy/Caddyfile` (bloco `header`) ou `frontend/nginx.conf`.
- **Cuidado:**
  - O ApexCharts injeta estilo inline e o tema também mexe no DOM.
  - Começar com `Content-Security-Policy-Report-Only` com `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`.
  - Navegar por todas as telas olhando o console e só então trocar para a política aplicada.
- **Teste:** um teste do Caddy/nginx não vale o custo. A verificação é o E2E da fase 2.6 rodando sem violação de CSP no console.

### 1.6 Registrar acesso negado

Vem de *Fundamentos de segurança da informação*: tentativa não autorizada deve ser
"rejeitada **e relatada**".

- **Problema:** hoje o log registra o que deu certo (senha redefinida, conta excluída). Login falho, throttle estourado e refresh revogado reutilizado não deixam rastro.
- **Mudança:**
  - `logger.warning` nesses três pontos (`CookieTokenObtainPairView` e `AuthScopedRateThrottle`).
  - O registro leva o identificador **mascarado** e o IP, nunca a senha nem o token.
- **Teste:** `assertLogs("core", "WARNING")` no login com senha errada, conferindo que a senha não aparece no texto.

---

## Fase 0: lint e piso de cobertura

Escopo decidido em 2026-11-02: só 0.3 e 0.4, ambos feitos nessa data.

**Fora desta fase:**
- **CI no GitHub Actions (antigo 0.1):** fica para depois. Até lá, lint, testes e cobertura rodam à mão (comandos abaixo).
- **`docs/testes.md` (antigo 0.2):** entra num plano próprio de revisão dos `.md` de `docs/`. Ele continua citado em `requirements-dev.txt` e `.coveragerc` sem existir.

Comandos, de dentro de `backend/`:
- **Lint:** `ruff check .`
- **Cobertura, no container:** `coverage run manage.py test`, seguido de `coverage combine` e `coverage report`. O relatório falha abaixo de 80%.

### 0.3 Linter Python — **feito**

Vem de *Revisões e análise estática*, que cita Flake8 e Pylint. O Ruff cobre os dois e é
o que as regras do projeto já pedem.

- **Mudança:** `ruff` no `requirements-dev.txt` e `[tool.ruff]` num `backend/pyproject.toml`.
- **Regras:**
  - Começar com `E`, `F`, `B`, `S` e `DJ`. `S` é o bandit embutido; `DJ` são as regras de Django.
  - Não reformatar o projeto de uma vez. `ruff check` primeiro, formatador depois, em commit separado, se houver.
- **Saldo existente:** o que já existir de aviso vai para `per-file-ignores` com o motivo, no mesmo espírito do `EXCEPTIONS.md` da acessibilidade.

**Como ficou:**
- **Configuração:** `backend/pyproject.toml`, com `ruff==0.17.3` no `requirements-dev.txt`. O limite de linha é 120, mas a E501 está desligada (fica para um formatador).
- **Ignorados por arquivo:** só as senhas fixas dos testes e o seed `create_dummy_data.py`.
- **Saldo de avisos:** decidiu-se corrigir em vez de ignorar. Dos 1.199 avisos iniciais, 1.006 eram linha longa e 105 eram senha fixa em teste ou no seed. Os ~85 restantes foram corrigidos no código:
  - imports sem uso e duplicados;
  - imports no meio do arquivo em `api.py`, `urls.py` e `settings.py`;
  - `raise ... from`;
  - variáveis `l`;
  - `zip(strict=True)`;
  - ordem dos models;
  - `except: pass` trocado por log;
  - `except Exception` estreitado nos serviços de cotação.
- **`noqa` que sobraram:** só os de falso positivo, cada um com o motivo: o import de signals nos `apps.py`, a `SECRET_KEY` sentinela e o `urlopen` com URL `https` fixa.
- **`Ativo.cnpj` (DJ001):** deixou de aceitar NULL, nas migrações `0005` (dados) e `0006` (esquema). O `Ativo.save` converte `None` em `''`, para que backups antigos continuem restaurando. Um teste em `test_import_service` trava isso.

### 0.4 Piso de cobertura, não meta — **feito**

*Teste na prática e TDD* avisa que perseguir percentual induz teste superficial e que
cobertura serve para validar a suíte depois.

- **Mudança:** `fail_under = 80` no `.coveragerc`, logo abaixo dos 82% atuais. Serve para travar regressão, não como objetivo.
- **O número que importa:** a lacuna por arquivo, sobretudo os da fase 2.

---

## Fase 2: testes guiados pelas técnicas das apostilas

### 2.1 Parser de extrato: de 5% para conjunto de referência

Combina o teste funcional sistemático (*Fundamentos de teste*) com o "critério de
aceitação medido por métrica sobre dados não vistos" (*Engenharia de sistemas
inteligentes*). O parser é heurística de classificação e tem os mesmos riscos de um
modelo.

- **Por que é o item de maior retorno:**
  - É a maior entrada de dado não confiável do sistema.
  - É onde já houve defeito real: o importador marcava lançamento futuro como realizado.
  - Está a 5%.
- **Mudança:**
  - Montar `core/tests/fixtures/extratos/` com PDFs **anonimizados**, um ou dois por banco suportado (Nubank, Santander, genérico), cada um com um `.json` ao lado com as linhas esperadas.
  - *Melhores práticas* pede avaliação de identificabilidade antes e depois. Trocar nomes, CPF e números de cartão, e conferir que a combinação de data e estabelecimento não identifica ninguém.
  - Um teste parametrizado compara a saída de `processar_pdf` com o `.json`.
  - Uma mudança de layout de banco é o equivalente a *drift*: quando acontecer, o PDF novo entra no conjunto **antes** da correção.
- **Casos de borda:**
  - PDF sem texto (escaneado).
  - PDF de página única.
  - Valor com milhar (`1.234,56`).
  - Estorno com sinal negativo.
  - Linha de data `31/12` numa fatura de janeiro.

### 2.2 Valor-limite nas regras com faixa e data

Particionamento em classes de equivalência mais valor-limite. *Fundamentos de teste*
recomenda esse par para sistemas críticos.

Alvos, com os limites que interessam:

| Regra | Onde | Limites a testar |
|---|---|---|
| Vencimento da fatura | `fatura_service.calcular_vencimento_fatura` | compra no dia do fechamento, no dia anterior e no seguinte; fechamento 28/29/30/31 em fevereiro; compra em dezembro que vence em janeiro |
| Recorrência mensal | `recorrencia_service` | início em 31/01 (fevereiro não tem 31); anual em 29/02 |
| Banda 5/25 | `investimento/sinais.py` | peso exatamente na borda (não acende), borda + 0,01 (acende); meta em que 25% da meta = 5 p.p. (20%) |
| Valor do lançamento | serializers de `Conta` | 0, 0,01, negativo, maior valor do `DecimalField`, 3 casas decimais |
| `_ja_ocorreu` | `ferramentas_api.py` | ontem, hoje, amanhã, com `timezone.localdate` congelado |

Regra da apostila a seguir: **uma classe inválida por caso**, para uma não esconder a
outra.

### 2.3 Propriedades monetárias com Hypothesis

O Hypothesis é citado em *Teste na prática*. Gerar entradas aleatórias acha os casos
que ninguém escreveria à mão.

- **Invariantes candidatos:**
  - a soma das parcelas de uma compra parcelada é igual ao total, sem perder centavo;
  - o preço médio depois de compra e venda total volta a zero;
  - o backup é idempotente: `exportar → importar → exportar` dá o mesmo `dados.json`, a menos de carimbos de data;
  - a projeção de saldo dia N+1 é igual ao dia N mais os lançamentos do dia N+1.
- **Custo:** `hypothesis` no `requirements-dev.txt`, com `max_examples` baixo no CI para não pesar.

### 2.4 Isolamento entre usuários testado de forma sistemática

Casos de abuso da modelagem de ameaças. É a *Elevation of Privilege* do STRIDE e o
IDOR (OWASP A01).

- **Situação atual:** 21 arquivos já testam que o usuário B não vê o dado do A, cada um à sua maneira e endpoint por endpoint. Um endpoint novo nasce sem esse teste se ninguém lembrar.
- **Mudança:**
  - Um teste único percorre `router.registry` dos dois apps, cria um objeto do usuário A e confirma que o B recebe 404 em `GET`, `PATCH` e `DELETE` do detalhe e não o vê na listagem.
  - Rota que não se encaixa entra numa lista de exceções com o motivo.

### 2.5 Teste de mutação pontual

Mutante que sobrevive indica lacuna na suíte (*Teste na prática*).

- **Ferramenta:** a apostila cita o mutpy, que está pouco mantido. Usar o `mutmut`.
- **Onde:** só em `fatura_service.py`, `investimento/calculators.py` e `projecao_service.py`, que são as regras de negócio essenciais.
- **Como:** rodar à mão, **fora do CI**, uma vez por trimestre ou antes de refatorar um desses arquivos. Cada mutante sobrevivente vira um teste ou um comentário dizendo por que é equivalente.

### 2.6 Frontend: poucos testes de componente e um E2E

*Teste na prática* ressalva que no frontend a pirâmide pode ser diferente e recomenda
E2E só para um ou outro cenário crítico, como o pedido no exemplo do iFood.

- **Componente:**
  - `@testing-library/react` com `jsdom` no Vitest, só para componentes com lógica de validação: o formulário de conta com Zod, `ui/Modal.jsx` (focus trap e Escape, que o `REPORT.md` lista como verificado à mão) e o formulário de senha.
  - Consultas por papel e nome acessível (`getByRole`), que também testam a acessibilidade.
- **E2E com Playwright:** dois fluxos.
  1. Login, criar conta a pagar, marcar como paga e ver o saldo do dashboard mudar.
  2. Importar um PDF do conjunto 2.1, aprovar na conciliação e ver o lançamento.
- **Quando:** à mão, antes de mexer em fluxo crítico, enquanto não houver CI.

---

## Fase 3: processo de uma pessoa só

### 3.1 Modelo de ameaças dos três fluxos críticos

É a prática 4 do SDL: decompor, ranquear com STRIDE e definir contramedidas.
*Melhores práticas* chama isso de item de maior alavancagem.

- **Arquivo:** `docs/seguranca.md`, seção "Modelo de ameaças".
- **Escopo:** login e sessão, importação (ZIP e PDF) e backup. Para cada um, levantar os limites de confiança, os ativos, uma tabela STRIDE com o controle existente ou faltante e o risco em probabilidade × impacto.
- **Saída:** os casos de abuso que saírem daqui viram testes, como os da 2.4 e os da 1.1.

### 3.2 ASVS como checklist

É a prática 5 do SDL. A apostila põe o L1 como cobertura do Top 10 e o L2 como
"a maior parte dos riscos".

- **Alvo:** L1 no sistema inteiro e L2 nos capítulos V2 (autenticação), V3 (sessão) e V12 (arquivos e upload).
- **Registro:** cada requisito marcado como atendido, não atendido ou não se aplica, com o arquivo que comprova. Mesmo formato parcial e honesto do `REPORT.md`.

### 3.3 Revisão sem par

*Revisões e análise estática* diz que revisão do próprio autor é *desktop checking* e
não conta como revisão. Num projeto solo não há par, então o objetivo é tirar o máximo
da auto-revisão.

- **Mudança:** `.github/pull_request_template.md` com checklist curto para código monetário e de entrada externa:
  - `Decimal`, nunca `float`;
  - arredondamento explícito;
  - fuso e data de competência;
  - idempotência de importador;
  - `usuario=request.user` no queryset;
  - erro logado e não devolvido cru;
  - teste de valor-limite.
- **Distância:** revisar o diff no dia seguinte, não logo depois de escrever. A apostila atribui o ganho da inspeção à leitura com distância e com checklist.

### 3.4 Registro de defeitos com análise causal

É o nível A do MPS-SW e a "revisão de incidentes anteriores" como insumo de requisito de
segurança (SDL, prática 2).

- **Arquivo:** `docs/defeitos.md`, uma entrada por defeito que chegou à base. Cada entrada tem o sintoma, a causa, por que os testes não pegaram e o que mudou para não repetir.
- **Primeiras entradas:**
  - as metas de alocação zeradas no restore de backup antigo;
  - receitas futuras marcadas como recebidas pelo importador;
  - o ajuste técnico de carteira que sumiu no restore.

### 3.5 Restore testado e runbook de incidente

Vem do plano de contingência de *Fundamentos de segurança da informação* e da prática
12 do SDL (resposta a incidentes).

- **Restore:**
  - O `docs/backup.md` explica o formato; falta o procedimento de crise.
  - Agendar um ensaio trimestral: restaurar o backup de produção numa base descartável e conferir a contagem por modelo.
  - Dois dos três defeitos da 3.4 vieram de restore, então isso não é teórico.
- **Runbook curto:**
  - vazou a `DJANGO_SECRET_KEY`: trocar a chave. Como ela é o `SIGNING_KEY` do SimpleJWT, todos os tokens deixam de valer e todo mundo precisa logar de novo. Os links de e-mail pendentes também expiram;
  - a base foi corrompida: aplicar o procedimento de restore;
  - surgiu uma dependência com CVE crítico: seguir o prazo da 1.4.

---

## Decisões em aberto

- **MFA (TOTP).**
  - *Fundamentos de segurança da informação* manda usar autenticação multifator a partir de criticidade média, e dado financeiro cabe nessa faixa.
  - O custo é real: modelo, fluxo de cadastro, códigos de recuperação e um passo a mais no backup.
  - Proposta: decidir depois da 3.1. Se o modelo de ameaças puser o roubo de senha no topo, entra.
- **DAST.**
  - Um `zap-baseline` do OWASP ZAP contra o ambiente local é barato e acharia cabeçalho faltante, como a CSP.
  - Fuzzing do parser (prática 10 do SDL) com `hypothesis` gerando bytes ainda é mais barato e cobre a superfície que importa.
  - Proposta: fuzzing dentro da 2.1, ZAP opcional.
- **Irretroatividade de lançamentos.**
  - *Fundamentos de segurança da informação* trata disso no contexto de fraude. Para um app pessoal, uma trilha "quem mudou a data de um lançamento passado" serve mais à conferência do que à segurança.
  - Fica fora até aparecer a necessidade.

## O que fica de fora, e por quê

- **CMMI, MPS-SW como certificação, PSIRT, equipe independente de teste de sistema, pentest formal (PTES), ICP-Brasil e carimbo do tempo:** são organizacionais. Deles se aproveita só a ideia que cabe numa pessoa, que já está nas fases 3.3 e 3.4.
- **PerSpecML, ML Canvas e MLOps:** o sistema não tem ML. Se a categorização automática de lançamentos vier a usar um modelo (o comando `categorizar_gastos_cartao`, hoje a 0% de cobertura, é o mais perto disso), estas são as exigências antes de começar:
  - especificar com PerSpecML;
  - critério de aceitação Dado/Quando/Então com piso de recall **por categoria**;
  - separação treino/teste **por data**;
  - a heurística atual como linha de base.

---

## Ordem sugerida

| # | Item | Tamanho | Depende de |
|---|---|---|---|
| 1 | 1.2 erro cru e 1.3 atomicidade | pequeno | — |
| 2 | 1.1 limites de upload | pequeno | — |
| 3 | 1.4 dependências | pequeno | — |
| 4 | ~~0.3 Ruff, 0.4 piso~~ — feito em 2026-11-02 | pequeno | — |
| 5 | ~~0.1 CI~~ — adiado; 0.2 vai para o plano de docs | — | — |
| 6 | 1.6 log de acesso negado | pequeno | — |
| 7 | 2.4 isolamento sistemático | médio | — |
| 8 | 2.1 conjunto de referência do parser | médio | 2 |
| 9 | 2.2 valor-limite | médio | — |
| 10 | 3.1 modelo de ameaças e 3.2 ASVS | médio | 1–7 (os achados já corrigidos entram como controle) |
| 11 | 1.5 CSP (Report-Only e depois aplicada) | pequeno | 12 para validar |
| 12 | 2.6 componente e E2E | grande | 8 |
| 13 | 2.3 Hypothesis, 2.5 mutação | médio | 9 |
| 14 | 3.3, 3.4, 3.5 processo | pequeno, contínuo | — |
