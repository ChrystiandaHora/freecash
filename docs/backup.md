# Backup e restauração `.fcbk`

Referência obrigatória antes de renomear qualquer modelo ou campo, e antes de tornar
qualquer FK obrigatória. O modo de falha aqui é o pior que existe: **a restauração não
dá erro** — devolve a base sem os registros.

---

## O formato

`.fcbk` é formato próprio, produzido por
[`export_service.py`](../backend/core/services/export_service.py):

```
JSON → zlib (nível 6) → AES-GCM → SHA256(payload) + payload → base64
```

A chave sai da senha do usuário por PBKDF2-HMAC-SHA256, 100.000 iterações, com salt
aleatório de 16 bytes. O nonce tem 12. O hash SHA256 vai **à frente** do payload
cifrado e é conferido antes de tentar decifrar — é o que separa "arquivo violado" de
"senha errada", duas mensagens diferentes para o usuário.

`VERSION = "4.1"` no export; o import aceita `{"4.0", "4.1"}`. A 4.0 é a mesma coisa
sem compressão, e por isso `decrypt_data_fcbk` trata `zlib.error` como sucesso
silencioso: um backup antigo simplesmente não estava comprimido.

---

## Quais modelos entram

Nenhuma lista manual. `get_backupable_models()` percorre os apps do projeto e pega todo
modelo que tenha **`usuario` e `uuid`**:

- `usuario` é o isolamento multi-tenant — sem ele não há como filtrar o que é de quem;
- `uuid` é a chave estável entre bases. Os `id` sequenciais mudam na restauração, então
  as FKs viajam no arquivo como `<campo>_uuid` e são religadas na chegada.

Consequência: **um modelo novo com esses dois campos entra no backup sozinho**. É o
comportamento certo, e é também por isso que a ordem precisa ser declarada à mão.

---

## O dict `priority` existe duas vezes

A ordem de restauração é a ordem das dependências: categoria antes de conta, carteira
antes de ativo, ativo antes de transação. Ela vive num dict `priority` que está
**duplicado** em `export_service.py` e `import_service.py`.

**Editar só um deixa a restauração meio quebrada.** O export ordena para gravar, o
import ordena para religar as FKs; se divergirem, um registro chega antes do pai e a FK
resolve para `None` — de novo, sem erro.

A exclusão prévia usa `reversed(backup_models)`, a mesma lista de trás para frente, para
que o filho saia antes do pai.

---

## Os quatro mapas de compatibilidade

O arquivo guarda **nomes de classe** (`data[app][NomeDoModelo]`) e **nomes de campo**.
Qualquer renomeação no código é, portanto, uma quebra de formato: o backup que o usuário
gerou ontem continua trazendo os nomes de ontem.

| Mapa | Para quê | Exemplo real |
|---|---|---|
| `NOMES_LEGADOS_DE_MODELO` | Modelo renomeado | `ReceitaRecorrente` → `LancamentoRecorrente` |
| `CAMPOS_RENOMEADOS_POR_MODELO` | Campo renomeado | `Conta.receita_recorrente_uuid` → `recorrencia_uuid` |
| `FKS_LEGADAS_COM_PADRAO` | FK que virou obrigatória | `Transacao.carteira`, que não existia antes das carteiras |
| `CAMPOS_MOVIDOS_DE_MODELO` | Campo que trocou de modelo | `Ativo.meta_porcentagem` → `PosicaoCarteira.meta_porcentagem` |

O terceiro é o mais traiçoeiro. O laço genérico grava `None` em toda FK cujo
`<campo>_uuid` não esteja no arquivo; com a coluna `NOT NULL`, o insert é rejeitado, o
fallback por nome também falha, e o registro entra em `total_ignorados` — **as ordens do
usuário somem sem erro nenhum**. Ver [carteiras.md](carteiras.md) para o caso concreto.

O quarto é o contra-exemplo do "remover campo é seguro". Quando a meta de alocação
saiu de `Ativo` para `PosicaoCarteira`, `filter_valid_fields` passou a descartá-la de
todo backup anterior — sem erro — e o balanceamento reabria com todos os ativos em 0%.
O valor é lido antes da filtragem e aplicado **depois** do recálculo, que é quem cria a
posição que vai recebê-lo. Só é aplicado quando o ativo tem exatamente uma posição: a
meta era global por ativo, e dividi-la entre custódias exigiria um critério que o
arquivo não tem.

**A próxima renomeação, a próxima FK obrigatória ou o próximo campo que muda de modelo
precisa da entrada correspondente.** `core/tests/test_backup_compatibilidade.py` cobre
os quatro casos.

Remover campo é seguro só quando o dado morreu de fato; se ele foi para outro modelo,
`filter_valid_fields` o descarta em silêncio e é preciso a entrada acima.

---

## Signals desconectados durante a importação

Dois conjuntos saem do ar dentro da transação, por motivos diferentes:

**Investimento.** `atualizar_ativo_apos_transacao` recalcularia preço médio a cada
transação reinserida, produzindo valores parciais enquanto o histórico ainda está
incompleto. O recálculo é forçado no fim, sobre o conjunto já completo — e é ele que
reconstrói `PosicaoCarteira`, que num backup anterior às carteiras nem existe no
arquivo.

**Fatura.** `_consolidar_fatura` criaria uma fatura nova, com UUID gerado na hora, para
cada compra de cartão restaurada — e ela depois duplicaria a fatura original que o
próprio backup traz. Por isso `deduplicar_faturas()` roda ao final.

---

## `AporteMeta` não passa pelo laço genérico

Ele não tem FK para o usuário — pertence à meta, não à pessoa. Fica fora da descoberta
automática e é exportado e restaurado à mão, religado pelo `meta_uuid`.

No `DELETE`, os aportes antigos já saem em cascata junto com as metas, então não há
passo de limpeza próprio.

Modelos com `usuario` OneToOne (só `ConfigUsuario` hoje) também escapam do `DELETE`: são
atualizados com `update_or_create`, porque apagar o perfil do usuário logado no meio de
uma restauração deixaria a sessão sem configuração.

---

## Tudo numa transação

`restore_user_data_fcbk` roda `DELETE` e `INSERT` dentro de `transaction.atomic`. Uma
falha no meio desfaz tudo — inclusive o apagamento. Restauração parcial seria pior que
restauração nenhuma: o usuário ficaria sem os dados antigos e sem os novos.

---

## O que ficou de fora, e por quê

**Não há backup automático nem versionado.** O usuário exporta quando quer; o sistema
guarda apenas `ConfigUsuario.ultimo_export_em`, para lembrá-lo.

**Não há merge.** A restauração é substituição total: apaga o que existe e repõe o do
arquivo. Mesclar duas bases exigiria decidir o que fazer com cada conflito, e não há
interface para essa decisão.

**A senha do arquivo não é a senha da conta.** São independentes de propósito — trocar a
senha da conta não deve invalidar backups já gerados. Em compensação, **senha de backup
perdida é backup perdido**: não há recuperação, por construção.
