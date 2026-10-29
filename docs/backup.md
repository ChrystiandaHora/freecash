# Backup e restauração (ZIP)

Referência obrigatória antes de renomear qualquer modelo ou campo, e antes de tornar
qualquer FK obrigatória. O modo de falha aqui é o pior que existe: **a restauração não
dá erro** — devolve a base sem os registros.

---

## O formato

O backup é um ZIP comum, cifrado com **AES-256** (WinZip AE-2), gerado por
[`export_service.py`](../backend/core/services/export_service.py):

```
freecash_meus-dados_<usuario>_<AAAA-MM-DD_HHMM>.zip
├── LEIA-ME.txt     como abrir, o que é cada arquivo e cada coluna
├── dados.json      {"metadata": {"formato": "freecash-dados", "version": "5.0", ...}, "data": {...}}
└── planilhas/      um CSV por entidade com registros: lancamentos.csv, ativos.csv, ...
```

Ele substituiu o `.fcbk`, formato próprio (JSON → zlib → AES-GCM → base64) que só o
freecash lia. O motivo foi a portabilidade: quem sai da plataforma precisa levar os
dados num formato que abra em outro lugar. O mesmo arquivo serve de backup e de
exportação — não há dois contratos para manter.

**A importação lê só o `dados.json`.** As planilhas e o LEIA-ME são para pessoas, gerados
a partir do mesmo dicionário por
[`backup_planilhas.py`](../backend/core/services/backup_planilhas.py): separador `;`,
vírgula decimal, datas `AAAA-MM-DD` e BOM UTF-8 (sem ele o Excel em português quebra os
acentos). Ao lado de cada coluna `<campo>_uuid` vai uma coluna `<campo>` com o nome do
registro referenciado. O nome do arquivo vem do `verbose_name_plural` do modelo, exceto
onde `NOMES_DAS_PLANILHAS` corrige (`Conta` → `lancamentos`).

### Por que AES-256, e por que senha de 12 caracteres

O ZIP com senha tem dois padrões. O **ZipCrypto** abre com duplo clique no Windows e no
macOS, mas é quebrável com ferramentas públicas — inaceitável para dados financeiros. O
**AES-256** é forte, mas o descompactador nativo do Windows e do macOS não o abre: é
preciso 7-Zip, WinRAR, Keka ou The Unarchiver. A tela e o LEIA-ME dizem isso.

O padrão WinZip AE-2 deriva a chave com só **1.000 iterações** de PBKDF2-SHA1 (o `.fcbk`
usava 100.000 de SHA-256), e isso não é configurável sem sair do padrão — e do que as
ferramentas comuns abrem. Quem compensa é a senha: a exportação exige de 12 a 128
caracteres, os mesmos limites da senha da conta (`TAMANHO_MINIMO` e `TAMANHO_MAXIMO` de
[`validacao_senha.py`](../backend/core/validacao_senha.py)).

Todas as entradas são cifradas, o LEIA-ME inclusive: ele cita nomes de categorias,
cartões e carteiras do usuário.

### Exportar: POST, com a senha no corpo

`POST /api/ferramentas/backup/` com `{"senha": "..."}`. Era um `GET` com `?senha=` na URL,
o que gravava a senha em log de acesso, proxy e histórico do navegador. O
`GET /api/ferramentas/exportar/` ficou só com os relatórios por período (Excel, CSV e
PDF), que não cobrem tudo e não voltam para o sistema.

Os dois têm throttle por usuário (`backup`: 10/hora; `relatorios`: 30/hora, em
`DEFAULT_THROTTLE_RATES`): cada pedido lê a base inteira do usuário. O
`GET /api/ferramentas/backup/` devolve `{"ultimo_backup_em": ...}` (de
`ConfigUsuario.ultimo_export_em`) para a tela lembrar quem está há mais de 30 dias sem
backup; ele fica fora do throttle, que existe para o custo de gerar, não de consultar. Exportar não passa
pelo portão de e-mail confirmado (ver [autenticacao.md](autenticacao.md)).

### Importar: com ou sem senha

`ler_backup_zip` em [`import_service.py`](../backend/core/services/import_service.py)
aceita ZIP cifrado e ZIP sem senha. O segundo caso é deliberado: um usuário que extrai o
backup, corrige algo no `dados.json` e recompacta numa ferramenta qualquer precisa
conseguir importar de volta.

Antes de restaurar, o arquivo passa por quatro portões, cada um com mensagem própria:
é ZIP; tem `dados.json`; a senha está presente e certa; e `metadata.formato` é
`freecash-dados` com versão em `SUPPORTED_VERSIONS`. O `dados.json` descompactado tem
teto de `TAMANHO_MAXIMO_DADOS_JSON` (100 MB) contra ZIP malicioso que infla ao abrir — e
a leitura para um byte além do teto, porque o tamanho declarado no cabeçalho pode mentir.

### O `dados.json` pode vir editado à mão

Com o `.fcbk` isso já era possível — quem tem a senha consegue montar um arquivo —, mas
o formato aberto torna o caminho óbvio. Por isso `filter_valid_fields` descarta **chave
primária e dono** de toda linha (`id`, `usuario`, `usuario_id`). Sem isso, uma linha com
`usuario_id` de outra pessoa era criada na conta dela — o `Model.__init__` do Django
aplica o `usuario_id` solto por cima do `usuario` passado pela restauração. As FKs
continuam vindo só por `<campo>_uuid`, resolvidas contra os registros do próprio
arquivo. `test_backup_zip.py` cobre os dois vetores.

---

## Quais modelos entram

`get_backupable_models()` percorre os apps do projeto e pega todo modelo que tenha
**`usuario` e `uuid`**:

- `usuario` é o isolamento multi-tenant — sem ele não há como filtrar o que é de quem;
- `uuid` é a chave estável entre bases. Os `id` sequenciais mudam na restauração, então
  as FKs viajam no arquivo como `<campo>_uuid` e são religadas na chegada.

Modelos que pertencem ao usuário por outro caminho ficam fora da descoberta e são
exportados e restaurados à mão: `AporteMeta` (via meta), `DetalheRendaFixa` e `Cotacao`
(via ativo) e `LinhaExtrato` (via extrato). A `LinhaExtrato` ficou de fora até 2026-10:
a restauração apagava os extratos, os recriava vazios e as linhas sumiam em cascata.

**Esquecer a exportação manual não dá erro.** Por isso
[`test_backup_cobertura.py`](../backend/core/tests/test_backup_cobertura.py) percorre
todos os modelos de `core` e `investimento` e falha se algum não estiver no backup nem
em `FORA_DO_BACKUP` — a lista de exclusões, cada uma com o motivo (hoje só
`LogAcaoAdmin`, que é auditoria da administração).

---

## A ordem de restauração

A ordem é a das dependências: categoria antes de conta, carteira antes de ativo, ativo
antes de transação. Ela vive no dict `priority` de `get_backupable_models`, num lugar
só — a exportação e a importação usam a mesma função. (Antes havia uma cópia em cada
serviço, e elas já tinham divergido.)

Um modelo novo sem entrada em `priority` vai para o fim. Se ele for **pai** de outro, a
FK do filho resolve para `None` — de novo, sem erro. Modelo novo com FK precisa de
entrada.

A exclusão prévia usa `reversed(backup_models)`, a mesma lista de trás para frente, para
que o filho saia antes do pai.

---

## Renomear modelo ou campo quebra os backups já gerados

O arquivo guarda **nomes de classe** (`data[app][NomeDoModelo]`) e **nomes de campo**.
Renomear no código, tornar uma FK obrigatória ou mover um campo de modelo faz o ZIP de
ontem perder dados na restauração de hoje — e `filter_valid_fields` descarta o que não
reconhece sem avisar.

Na época do `.fcbk` havia quatro mapas de compatibilidade para isso
(`NOMES_LEGADOS_DE_MODELO`, `CAMPOS_RENOMEADOS_POR_MODELO`, `FKS_LEGADAS_COM_PADRAO` e
`CAMPOS_MOVIDOS_DE_MODELO`). Saíram junto com o `.fcbk`: nenhum arquivo daquela época
chega mais, e eles eram código morto. **A próxima mudança desse tipo precisa trazer o
mapa de volta** — o histórico do git tem a implementação e os testes
(`test_backup_compatibilidade.py`) — e subir `VERSION`.

O formato atual é a versão `5.0`.

---

## Signals desconectados durante a importação

Dois conjuntos saem do ar dentro da transação, por motivos diferentes:

**Investimento.** `atualizar_ativo_apos_transacao` recalcularia preço médio a cada
transação reinserida, produzindo valores parciais enquanto o histórico ainda está
incompleto. O recálculo é forçado no fim, sobre o conjunto já completo — e é ele que
reconstrói `PosicaoCarteira`, que é cache.

**Fatura.** `_consolidar_fatura` criaria uma fatura nova, com UUID gerado na hora, para
cada compra de cartão restaurada — e ela depois duplicaria a fatura original que o
próprio backup traz. Por isso `deduplicar_faturas()` roda ao final.

---

## Modelos fora do laço genérico

`AporteMeta`, `LinhaExtrato`, `Cotacao` e `DetalheRendaFixa` não têm FK para o usuário e
são restaurados à mão depois do laço, religados pelo UUID do pai. No `DELETE`, os
registros antigos já saem em cascata junto com o pai, então não há passo de limpeza
próprio.

Modelos com `usuario` OneToOne (só `ConfigUsuario` hoje) também escapam do `DELETE`: são
atualizados com `update_or_create`, porque apagar o perfil do usuário logado no meio de
uma restauração deixaria a sessão sem configuração.

Nem todo campo de `ConfigUsuario` volta do arquivo. `CAMPOS_DE_ESTADO_DA_CONTA` lista os
que descrevem a conta, e não os dados — `email_verificado`, `email_verificado_em` e
`email_pendente` —, e a restauração mantém os valores atuais deles. O caso que motivou:
um backup gerado antes da confirmação do e-mail trazia `email_verificado: False`, a
restauração gravava isso por cima, e a importação seguinte era recusada com 403 pelo
`EmailVerificadoOuCarencia` assim que a carência tivesse passado. O inverso também
vale: um backup de conta confirmada não confirma a conta atual. As preferências
(`moeda_padrao`) continuam vindo do arquivo. `core/tests/test_backup_estado_conta.py`
cobre os dois sentidos.

---

## Tudo numa transação

`restaurar_dados_usuario` roda `DELETE` e `INSERT` dentro de `transaction.atomic`. Uma
falha no meio desfaz tudo — inclusive o apagamento. Restauração parcial seria pior que
restauração nenhuma: o usuário ficaria sem os dados antigos e sem os novos.

---

## O que ficou de fora, e por quê

**Não há backup automático nem versionado.** O usuário exporta quando quer; o sistema
guarda apenas `ConfigUsuario.ultimo_export_em`, para lembrá-lo.

**Não há merge.** A restauração é substituição total: apaga o que existe e repõe o do
arquivo. Mesclar duas bases exigiria decidir o que fazer com cada conflito, e não há
interface para essa decisão.

**A importação não lê os CSVs.** Eles perdem informação de propósito (vírgula decimal,
rótulos ao lado dos UUIDs) para serem legíveis; o contrato de máquina é o `dados.json`.

**`.fcbk` não é mais lido.** A decisão foi cortar por completo, sem período de
transição: quem tinha um `.fcbk` precisava restaurá-lo e exportar de novo antes do
deploy desta mudança.

**A senha do arquivo não é a senha da conta.** São independentes de propósito — trocar a
senha da conta não deve invalidar backups já gerados. Em compensação, **senha de backup
perdida é backup perdido**: não há recuperação, por construção.
