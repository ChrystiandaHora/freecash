# Autenticação, identidade e administração

Documento de referência para quem for mexer em login, sessão, confirmação de
e-mail, redefinição de senha ou no painel administrativo. Descreve o que o sistema
faz, **por que** faz assim e quais são os limites conhecidos.

---

## Identidade

O login aceita **e-mail ou nome de usuário**, resolvido por
`core/auth_backends.py::EmailOuUsernameBackend`.

O modelo de usuário continua sendo o `auth.User` padrão do Django. Trocar por um
`AUTH_USER_MODEL` customizado com `USERNAME_FIELD = "email"` foi avaliado e
descartado: as migrations iniciais de `core` e `investimento` já declaram
dependência *swappable* de `auth.User`, e há chave estrangeira para o usuário em
praticamente todos os modelos. Trocar o modelo com migrations aplicadas exigiria
copiar a tabela preservando as chaves primárias, reapontar as referências e
reconstruir os tipos de conteúdo — procedimento que a documentação do Django
descreve como não suportado. O ganho seria nulo: `auth.User` sempre teve `email`.

**A unicidade do e-mail é imposta em duas camadas**, porque não é possível
adicionar `Meta.constraints` a um modelo de aplicativo terceiro:

1. `core/serializers_auth.py` valida e normaliza (`strip().lower()`);
2. a migration `core/0010_email_unico_case_insensitive` cria um índice único
   **parcial** sobre `LOWER(email)`, com `WHERE email <> ''`.

O `WHERE` é o que permite conviver com as contas criadas antes de o e-mail passar a
ser obrigatório e com `createsuperuser --noinput`, que não exige endereço. Sem essa
unicidade, o login por e-mail seria ambíguo — por isso a ordem importa: a
unicidade é pré-requisito do backend de autenticação, não um detalhe posterior.

O estado de identidade (`email_verificado`, `email_verificado_em`,
`email_pendente`) fica em `ConfigUsuario`, que já é o perfil um-para-um do usuário.
O endereço confirmado permanece em `User.email`, onde o Django e o gerador de token
de redefinição esperam encontrá-lo.

---

## Sessão

| Item | Valor | Onde |
|---|---|---|
| Access token | 15 minutos, em memória no cliente | `SIMPLE_JWT` |
| Refresh token | 7 dias, cookie HttpOnly | `core/views/cookies.py` |
| Rotação | ativa, com blacklist do token anterior | `SIMPLE_JWT` |
| Path do cookie | `/api/token/` | `AUTH_COOKIE_PATH` |

O `path` do cookie **precisa** cobrir `/api/token/clear/`. Ele já foi
`/api/token/refresh/`, e por casamento de prefixo o navegador nunca o enviava ao
endpoint de logout — o servidor não tinha como ler o token que deveria revogar. O
logout apenas apagava o cookie no navegador, e uma cópia do refresh token seguia
válida por sete dias.

`rest_framework_simplejwt.token_blacklist` **precisa** estar em `INSTALLED_APPS`.
`BLACKLIST_AFTER_ROTATION` já estava ligado sem o app instalado, e nessa
configuração a blacklist é silenciosamente inerte: nada é registrado, nada é
revogável.

### Limites conhecidos da revogação

`core/services/auth_service.py::revogar_tokens_do_usuario` encerra as sessões de
uma conta. Duas limitações reais:

1. **O access token sobrevive até 15 minutos.** Sendo stateless, ele não é
   revogável — a janela é inerente a JWT sem introspecção. Vale para a troca de
   senha. **Não** vale para suspensão de conta: o `JWTAuthentication` do SimpleJWT
   verifica `is_active` a cada requisição, então o suspenso para na chamada
   seguinte.
2. **Tokens emitidos antes de o app de blacklist existir** não têm registro em
   `OutstandingToken` e não são alcançáveis. Eles expiram naturalmente dentro dos
   sete dias do refresh token.

---

## Confirmação de e-mail

Fluxo: cadastro → e-mail com link para o SPA → `POST /api/auth/verificar-email/`.

O token é HMAC, sem armazenamento
(`core/services/tokens.py::EmailVerificationTokenGenerator`). O uso único sai de
graça porque `_make_hash_value` inclui o próprio `email_verificado` no valor
assinado: concluir a verificação altera esse estado e invalida o token. **Se
alguém simplificar aquele método, o uso único desaparece** — o teste
`test_token_deixa_de_valer_apos_a_confirmacao` é o que acusa a regressão.

Duas decisões que parecem detalhes e não são:

- **O link aponta para o frontend, e a confirmação é `POST`.** Clientes de e-mail e
  filtros corporativos pré-carregam URLs das mensagens; com um `GET` no endpoint, o
  token seria consumido antes de o usuário clicar.
- **A rota React `/verificar-email/:uid/:token` fica fora de `PublicRoute` e de
  `ProtectedRoute`.** Quem clica no link costuma já estar logado, e o
  `PublicRoute` mandaria essa pessoa para `/dashboard` sem nunca confirmar o
  endereço — o link falharia justamente no caso mais comum.

**Quem não confirmou consegue entrar.** Bloquear o login seria pior: a conta já
nasce com o ecossistema financeiro provisionado, e a pessoa não conseguiria entrar
nem para pedir novo link — o reenvio precisaria ser aberto, virando um endpoint
para descobrir quem tem conta e disparar mensagens contra terceiros.

A exigência aparece **apenas na importação**, e só depois de
`EMAIL_VERIFICATION_GRACE_DAYS`, via `core/permissions.py::EmailVerificadoOuCarencia`.

O critério é amplificação, não importância:

- **CRUD financeiro** nunca é bloqueado. Impedir o dono de registrar os próprios
  lançamentos pune quem tem os dados sem proteger ninguém.
- **Exportar** também não é bloqueado. `export_user_data` percorre só os registros do
  próprio usuário, então uma conta descartável — que não tem dados — exporta nada.
  O portão esteve aplicado ali por engano, e bloqueava justamente o backup que a tela
  de exclusão de conta manda fazer antes de apagar tudo.
- **Importar** é bloqueado. Recebe arquivo enviado pelo usuário e o processa com
  leitores de PDF e de planilha, gastando CPU e memória por requisição.

**Caso de borda das contas legadas:** contas criadas antes de o e-mail virar
obrigatório não têm endereço nenhum. Para elas, "confirme seu e-mail" é um beco sem
saída — não há e-mail a confirmar, e o endpoint de reenvio recusa a operação. A
mensagem de recusa passa a apontar para Minha Conta, onde a pessoa cadastra um
endereço e recupera, junto, a capacidade de redefinir a senha.

---

## Redefinição de senha

Usa o `default_token_generator` do Django, sem subclasse. `_make_hash_value` já
inclui o hash da senha e o `last_login`, então trocar a senha invalida o token —
uso único nativo, stateless.

**O pedido nunca revela se a conta existe.** `POST /api/auth/senha/reset/` responde
sempre `202` com a mesma mensagem, para endereço cadastrado, desconhecido ou de
conta inativa. Num sistema financeiro, confirmar que um endereço tem conta já é
informação sensível. Qualquer "404 amigável" adicionado aqui transforma o endpoint
num verificador de contas — o teste `test_resposta_identica_para_email_inexistente`
compara corpo e status dos dois casos.

Há uma assimetria deliberada: o registro **pode** dizer que um nome de usuário está
em uso (a tela de login já revela o mesmo pela resposta de autenticação), mas
**não** pode dizer que um e-mail está cadastrado.

Concluída a troca, todas as sessões da conta são revogadas — se a senha vazou, o
invasor cai junto — e `email_verificado` passa a `True`, porque quem abriu o link
provou ter acesso à caixa de entrada.

---

## Gestão da própria conta

Tela `/conta`, alcançada pelo avatar no cabeçalho. Quatro operações, em
`core/views/conta_api.py`.

**Três delas exigem a senha atual**: trocar e-mail, trocar senha e excluir a
conta. Quem alcança uma sessão aberta — uma máquina destravada, um token vazado —
consegue tudo o que a sessão consegue; a senha transforma essas ações em algo que
só o dono faz.

Editar nome de usuário e moeda **não** pede senha, de propósito. Exigi-la a cada
ajuste de preferência treinaria o usuário a digitá-la sem pensar, o que enfraquece
a proteção justamente onde ela importa.

### Troca de e-mail

O endereço novo vai para `ConfigUsuario.email_pendente` e **só substitui
`User.email` quando o link enviado a ele é aberto**. Enquanto isso, o endereço
antigo continua servindo para entrar e recuperar a conta.

Isso protege dois cenários concretos: um erro de digitação não deixa a conta sem
endereço válido para recuperação, e quem tomasse uma sessão não conseguiria trocar
o e-mail e trancar o dono para fora — que seria a tomada definitiva da conta, já
que é o e-mail que recebe a redefinição de senha.

Concluída a troca, um aviso vai para o **endereço antigo**. É a rede de segurança
de quem não pediu a troca, e o único canal que ainda o alcança.

O token usa `EmailChangeTokenGenerator`, **separado** de
`EmailVerificationTokenGenerator`. A separação é de correção, não de organização:
aquele assina o endereço vigente, este assina o pendente. Reaproveitar um único
gerador permitiria que um link de verificação comum confirmasse uma troca de
e-mail. O teste `test_token_de_verificacao_comum_nao_confirma_troca` guarda isso.

Cancelar uma troca pendente limpa `email_pendente` e, com isso, **invalida o link
já enviado** — porque o valor pendente entra no hash do token.

### Troca de senha

Exige a senha atual, recusa uma nova senha igual à atual, e aplica os
`AUTH_PASSWORD_VALIDATORS`.

Ao concluir, **todas as sessões são revogadas** e uma sessão nova é devolvida a
quem fez a troca. Revogar é o ponto: se a senha vazou, manter as sessões abertas
preservaria o acesso do invasor no exato momento em que a vítima acredita ter
resolvido o problema. Devolver uma sessão nova evita deslogar quem acabou de
provar ser o dono, o que seria hostil sem ganho de segurança.

### Sessões ativas

`GET /api/auth/sessoes/` conta os refresh tokens vivos do usuário; a query sai do
próprio app de blacklist do SimpleJWT, sem modelo novo:

```python
OutstandingToken.objects.filter(
    user=usuario, expires_at__gt=timezone.now(), blacklistedtoken__isnull=True
).count()
```

**A contagem superestima, e a interface diz isso.** Com `ROTATE_REFRESH_TOKENS`, uma
sessão em uso contribui com exatamente um token — cada renovação revoga a anterior.
Mas uma sessão abandonada sem logout deixa o último token pendente até expirar, e
segue contada por até sete dias. Por isso o rótulo fala em "dispositivos conectados
nos últimos 7 dias" em vez de afirmar precisão que o dado não tem.

`POST /api/auth/sessoes/encerrar-outras/` revoga **todas** as sessões e emite uma
nova para quem chamou. Revogar tudo não é descuido: o cookie do refresh token é
gravado com `path=/api/token/` e não é enviado a esta rota, então não há como
identificar qual token pendente pertence a quem está pedindo. Alargar o path
resolveria a identificação ao custo de expor o refresh token a todas as rotas de
dados; revogar tudo e devolver uma sessão nova chega ao mesmo resultado observável
sem ampliar essa superfície. É o mesmo mecanismo da troca de senha.

O cliente **precisa** gravar o `access` devolvido (`setAccessToken`), senão a própria
aba cai na requisição seguinte — ela também foi revogada.

### Exclusão de conta

Exige a senha atual **e** o nome de usuário digitado por extenso. A ação é
irreversível e apaga anos de histórico financeiro; um clique acidental não pode
bastar.

**Pré-requisito que estava quebrado:** excluir qualquer usuário era impossível. Os
receivers de `post_delete` de `Conta` e `Categoria` chamavam `atualizar_config`,
que faz `get_or_create` da `ConfigUsuario` — durante o cascade isso **recriava** a
configuração apontando para uma linha de `auth_user` sendo apagada na mesma
transação, e o commit falhava com violação de chave estrangeira.

A correção é `atualizar_config_existente`, que usa `filter().update()` e é no-op
quando não há linha. Os receivers de `post_save` seguem usando `atualizar_config`,
porque ali criar a configuração ausente é aceitável. `test_exclusao_usuario.py`
cobre a causa raiz, e não apenas o sintoma.

---

## Rate limiting

Opt-in por view, nunca global: `DEFAULT_THROTTLE_CLASSES` fica vazio para não
estrangular o uso normal do aplicativo.

| Escopo | Limite |
|---|---|
| `login` | 10/min |
| `register` | 10/hora |
| `senha_reset` | 5/hora por IP |
| `senha_reset_email` | 3/hora por endereço de destino |
| `email_verify_resend` | 3/hora |

O limite por endereço de destino existe porque o limite por IP, isolado, não
protege o destinatário: sem ele, o sistema serviria de disparador de mensagens
contra alguém.

**O cache do throttle é `DatabaseCache`**, no alias `throttle`. `LocMemCache` é por
processo: com N workers do gunicorn o limite efetivo viraria N× e zeraria a cada
reload. A tabela é criada por `manage.py createcachetable` — **comando, não
migration**, por isso precisa constar no compose e em qualquer procedimento de
deploy.

---

## Painel administrativo

O papel é a flag `is_staff` do `auth.User`, verificada por
`core/permissions.py::IsAdminPlataforma`. A suspensão é `is_active=False`.

**O papel nunca vem de claim do JWT.** Com `ROTATE_REFRESH_TOKENS`, o SimpleJWT
reaproveita o payload do refresh na rotação, trocando apenas `jti` e `exp` — um
papel embutido no token sobreviveria por até sete dias, e um administrador
rebaixado continuaria administrador por uma semana. O frontend lê o papel de
`GET /api/auth/me/`, que consulta o banco.

O gate `AdminRoute` no React é conveniência de navegação. **O enforcement é a
permission class no servidor.**

### Fronteira de privacidade

Os endpoints `/api/admin/*` expõem **apenas metadados de conta**: identificação,
datas, estado de verificação, estado de atividade e contagens de volume. Nunca
transações, saldos, ativos ou valores. Administrar a plataforma não exige ver as
finanças de ninguém.

Os serializers em `core/serializers_admin.py` declaram os campos um a um e nunca
usam `fields = "__all__"` — com `__all__`, adicionar um campo a um modelo o
publicaria automaticamente na API do painel. O teste
`test_api_admin.py::test_resposta_nao_expoe_dado_financeiro` é a proteção
automática dessa fronteira.

Toda ação administrativa grava um `LogAcaoAdmin`, com chaves `SET_NULL` para que
apagar a conta de um administrador não apague o histórico do que ele fez.

O `/admin/` do Django é registrado **somente quando `DEBUG=True`**: nenhum modelo
está registrado nele, e manter a rota em produção seria oferecer um formulário de
login a mais para atacar sem entregar nada em troca.

---

## Envio de e-mail

`core/services/email_service.py`, com o backend SMTP padrão do Django. Resend,
Brevo, SES e Postmark todos oferecem SMTP, então trocar de fornecedor é mudança de
variável de ambiente. Entregabilidade (SPF, DKIM, DMARC) se resolve no DNS.

Duas garantias, ambas com teste próprio:

- **Nada sai antes do commit.** Todo envio é agendado com
  `transaction.on_commit`. Sem isso, um erro posterior no `atomic` desfaria a
  criação da conta e o usuário receberia, ainda assim, confirmação de uma conta
  inexistente.
- **Falha de envio não derruba a requisição.** Servidor de e-mail fora do ar não
  pode impedir um cadastro; a conta existe e todo fluxo oferece "reenviar".

O envio ocorre em thread (`EMAIL_ASYNC=True`), seguindo a doutrina já documentada
em `core/services/recorrencia_service.py`: sem Celery, o trabalho é materializado
no próprio request. E-mail transacional é o caso mais tolerante a isso — volume
ínfimo e recuperação nativa. **Nos testes, `EMAIL_ASYNC=False`**: com thread,
`mail.outbox` é lido antes do envio terminar e o teste fica intermitente.

Em `TestCase`, o envio só acontece dentro de `self.captureOnCommitCallbacks(execute=True)`
— a transação do teste nunca é confirmada, então os callbacks de `on_commit` não
rodariam.

---

## Paginação

`PadraoPageNumberPagination` é **opt-in por requisição**: sem o parâmetro `page`, a
resposta continua sendo um array puro.

A escolha é deliberada. Ativar o envelope `{count, next, previous, results}`
globalmente mudaria o formato de ~20 pontos de consumo no frontend de uma vez, e
qualquer um não atualizado passaria a renderizar tabela vazia — ou, pior, mostraria
os primeiros 100 lançamentos como se fossem o total, levando a conclusões
financeiras erradas sem sinal de que faltam dados. **Truncar silenciosamente uma
lista financeira é pior do que não paginar.**

Os endpoints novos do painel administrativo nascem paginados (`AdminPaginacao`
sempre devolve o envelope).

**Pendência conhecida:** as telas que realmente precisam de paginação — extrato,
contas a pagar, receitas, compras de cartão e transações de investimento —
continuam pedindo a lista completa. Migrá-las exige trabalho de interface (controles
de página em cada tabela) e é tarefa própria.

---

## Variáveis de ambiente

Ver `.env_example`, que documenta todas. Com `DJANGO_DEBUG=False`, `settings.py`
valida a configuração no boot e **recusa iniciar** se faltar `DJANGO_SECRET_KEY`
real, credenciais de banco ou `DJANGO_ALLOWED_HOSTS` — falhar de imediato é melhor
que subir em produção com a chave de desenvolvimento assinando os tokens de sessão.
