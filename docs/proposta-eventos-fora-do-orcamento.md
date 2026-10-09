# Proposta: gastos de evento fora do orçamento mensal

> Status: **Implementada com sucesso**. Ver detalhes arquiteturais e operacionais em [`docs/eventos.md`](file:///Users/chrystianthalessantosdahora/Documents/projetoPessoal/freecash/docs/eventos.md). Registra gastos extraordinários (viagens, reformas, festas) mantendo o saldo de caixa correto sem distorcer KPIs, médias de 6 meses, DRE ou custo de vida das metas.

## 1. O problema

Em out/2026 o Horizonte de Saldos mostrava saldo projetado de **R$ 39.857,06**. Parte
desse dinheiro estava guardada e foi gasta numa viagem: cerca de **R$ 11 mil**.

Se as compras forem lançadas como despesas comuns, nas datas reais:

- o saldo fica certo (cai ~R$ 11 mil);
- mas o mês da viagem passa a ter uma despesa enorme, que estoura os KPIs do dashboard,
  as séries de 6 meses, o DRE, o relatório exportado **e o custo de vida médio usado nas
  metas**. A meta de reserva de emergência, por exemplo, passaria a mirar um valor maior
  sem motivo.

Hoje não há como dizer ao sistema "este gasto é real, mas não é do dia a dia". As
agregações de período somam toda despesa da janela, sem olhar flag nem categoria.

### Por que não usar o truque do ajuste de carteira

O ajuste técnico de carteira foi lançado em **2023-12-31**, antes do primeiro lançamento
do histórico, para entrar no saldo e ficar fora de toda janela de relatório. Funciona para
uma correção pontual, mas não para a viagem:

- a data real das compras se perde (vai só no texto da descrição);
- as compras aparecem em 2023 nas listagens;
- não dá para responder "quanto custou a viagem?" de forma confiável;
- não escala: a cada viagem, o mesmo improviso.

## 2. A ideia central: separar duas perguntas

O sistema já responde a duas perguntas diferentes, por caminhos diferentes:

| Pergunta | Quem responde | O gasto da viagem… |
|---|---|---|
| **Quanto dinheiro eu tenho?** | `saldo_liquidez_ate` → saldo atual, Horizonte de Saldos, patrimônio do BI | **entra** (o dinheiro saiu de verdade) |
| **Quanto eu gasto num mês normal?** | totais, séries, despesas por categoria, DRE, relatório, custo de vida das metas | **sai** (não é recorrente) |

`saldo_liquidez_ate` ([dashboard_helper.py](../backend/core/services/dashboard_helper.py))
soma tudo desde o início, sem data de começo; os relatórios trabalham sempre com janelas
fechadas. Basta então dar um nome ao gasto "fora do orçamento" e excluí-lo **só do segundo
grupo**.

## 3. Formas de marcar o gasto

### A. Flag na Categoria (`Categoria.fora_dos_relatorios`)

- **Prós:** mudança mínima; marca-se uma vez a categoria "Viagem" e pronto.
- **Contras:**
  - uma viagem é um *evento*, não uma *categoria*. Perde-se o detalhe por categoria dentro
    dela (hospedagem, alimentação, transporte);
  - `Conta.categoria` usa `on_delete=SET_NULL`: se a categoria for apagada, os gastos voltam
    **em silêncio** para os KPIs.

### B. Flag no lançamento (`Conta.extraordinario`)

- **Prós:** controle fino; a categoria normal continua valendo.
- **Contras:**
  - é preciso marcar compra por compra;
  - não agrupa nada: "quanto custou a viagem?" continua sem resposta.

### C. Evento (**recomendada**)

Um modelo novo, `Evento`, e um vínculo opcional `Conta.evento`.

- **Prós:**
  - responde às duas necessidades: tira o gasto dos KPIs **e** dá o total da viagem, com
    orçamento previsto e comparação com o realizado;
  - as compras mantêm a categoria normal, então dá para ver a viagem por categoria;
  - serve para outros casos: reforma, casamento, mudança, tratamento médico.
- **Contras:** mais trabalho, com modelo, migration, uma tela simples e um seletor nos
  formulários.

## 4. Esboço da opção C

### 4.1 Modelo

```python
class Evento(AuditoriaModel):
    """Agrupa gastos de uma ocasião (viagem, reforma) pagos fora do orçamento mensal.

    Atributos:
        fora_dos_relatorios: Se True, os lançamentos do evento entram no saldo, mas não
            nas agregações de período (dashboard, DRE, séries, custo de vida).
        orcamento: Valor previsto para o evento, para comparar com o realizado.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="eventos"
    )
    nome = models.CharField(max_length=100)          # "Viagem Europa 2026"
    inicio = models.DateField(null=True, blank=True)
    fim = models.DateField(null=True, blank=True)
    orcamento = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fora_dos_relatorios = models.BooleanField(default=True)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["-inicio", "nome"]


class Conta(AuditoriaModel):
    ...
    evento = models.ForeignKey(
        "core.Evento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
    )
```

Duas escolhas de propósito:

- **`PROTECT`:** não dá para apagar um evento que ainda tem lançamentos. Assim nenhum gasto
  volta para os KPIs sem você perceber (o problema da opção A).
- **`fora_dos_relatorios` no evento, não fixo:** um evento também pode servir só para
  agrupar gastos sem tirá-los dos KPIs, por exemplo um "Natal 2026" que você quer ver
  junto, mas que faz parte do orçamento.

### 4.2 A regra num lugar só

O maior risco de qualquer opção é **esquecer alguma soma**. Por isso a exclusão fica num
método do QuerySet, e não repetida em cada consulta:

```python
class ContaQuerySet(models.QuerySet):
    def do_orcamento(self):
        """Exclui gastos de eventos marcados como fora dos relatórios (ver docs/eventos.md)."""
        return self.exclude(evento__fora_dos_relatorios=True)


class Conta(AuditoriaModel):
    objects = ContaQuerySet.as_manager()
```

Cada agregação de período passa a começar por `Conta.objects.do_orcamento().filter(...)`.
Quem precisa ver tudo continua com `Conta.objects.filter(...)`.

### 4.3 Onde aplicar

Levantamento feito nos pontos que agregam `Conta` no backend.

**Passam a usar `do_orcamento()`:**

| Arquivo | Função | Por quê |
|---|---|---|
| [dashboard_helper.py](../backend/core/services/dashboard_helper.py) | `totals_for_range_competencia`, `totals_for_range_realizadas` | KPIs do mês |
| | `serie_por_dia_competencia`, `serie_por_dia_realizadas` | gráfico diário |
| | `serie_6m_competencia`, `serie_6m_realizadas` | gráfico de 6 meses |
| | `serie_fluxo_projetado_competencia` | fluxo projetado |
| | `despesas_por_categoria` | pizza/ranking de categorias |
| | `resumo_ultimos_3_meses_competencia` | resumo trimestral |
| [api.py](../backend/core/views/api.py) | `RelatoriosDREAPIView.get` | DRE de 12 meses |
| | `PlanoMetasAPIView` (custo médio) | **evita inflar o custo de vida** e a meta de reserva |
| [metas_service.py](../backend/core/services/metas_service.py) | usa `totals_for_range_competencia` | herda automaticamente |
| [export_report_service.py](../backend/core/services/export_report_service.py) | `get_despesas_por_categoria`, `get_comparativo_mensal_data` | relatório PDF |

**Continuam vendo tudo:**

| Arquivo | Função | Por quê |
|---|---|---|
| [dashboard_helper.py](../backend/core/services/dashboard_helper.py) | `saldo_liquidez_ate` | o dinheiro saiu de fato |
| [projecao_service.py](../backend/core/services/projecao_service.py) | `horizonte_saldos`, `calendario_mes` | fluxo de caixa real |
| [api.py](../backend/core/views/api.py) | `SaldoAtualAPIView`, liquidez do BI executivo | patrimônio |
| [fatura_service.py](../backend/core/services/fatura_service.py) | todas | a fatura cobra o valor cheio |
| listagens (Transações, Contas a pagar) | — | mostram o gasto, com um selo do evento |

Em `export_report_service.get_movimentacoes` vale decidir: é uma lista de movimentações,
então o natural é **mostrar** os lançamentos com a marca do evento, mas sem somá-los nos
totais do período.

### 4.4 O ponto delicado: compras no cartão

Se parte da viagem foi no cartão, o dashboard não soma a compra individual. Ele soma a
**fatura** (`eh_fatura_cartao=True`), que já inclui a compra da viagem. As compras
individuais de cartão são deliberadamente ignoradas (ver [fatura-cartao.md](fatura-cartao.md)).
Nesse caso o `exclude` não basta: é preciso abater da fatura o valor das compras do
evento, **só nos relatórios**.

Para os totais, uma anotação na fatura:

```python
# Valor da fatura sem as compras de eventos fora do orçamento
extra = Subquery(
    Conta.objects.filter(
        cartao=OuterRef("cartao"),
        data_prevista=OuterRef("data_prevista"),
        eh_fatura_cartao=False,
        evento__fora_dos_relatorios=True,
    )
    .values("cartao")
    .annotate(t=Sum("valor"))
    .values("t")
)
faturas.annotate(valor_orcamento=F("valor") - Coalesce(extra, Value(0)))
```

Para despesas por categoria, `_explodir_fatura_por_categoria` já abre a fatura nas compras
que a compõem. Basta ele **ignorar as compras do evento antes de calcular o fator
proporcional** e usar `valor_orcamento` no lugar de `fatura.valor`.

O saldo continua usando o valor cheio da fatura, porque foi o que saiu da conta.

Se toda a viagem foi paga com dinheiro guardado (Pix/débito), esse passo pode ficar para
depois, mas vale já estar previsto para a próxima viagem.

### 4.5 Backup e restore

O backup exporta os modelos de `get_backupable_models()` em
[import_service.py](../backend/core/services/import_service.py). É preciso:

- incluir `Evento` no backup, com prioridade **antes** de `Conta` (por causa da FK);
- remapear `Conta.evento` no restore, como já é feito com categoria e cartão;
- aceitar backups antigos sem o campo (ficam com `evento=None`).

Sem isso, um restore apaga os vínculos e a viagem volta inteira para os KPIs. É o mesmo
tipo de perda que aconteceu com as metas de alocação.

## 5. Para o gasto não sumir de vista

Tirar o gasto dos KPIs não deveria escondê-lo:

1. **Dashboard:** uma linha discreta abaixo dos KPIs, por exemplo
   *"Fora do orçamento neste mês: R$ 11.000,00 (Viagem Europa 2026)"*, com link para o
   evento. Assim o mês "bonito" não engana.
2. **Formulários de despesa** ([ContaPagarForm.jsx](../frontend/src/pages/forms/ContaPagarForm.jsx),
   [CompraCartaoForm.jsx](../frontend/src/pages/forms/CompraCartaoForm.jsx)): um campo
   *"Evento (opcional)"*, com texto de ajuda curto: "Gastos de evento entram no saldo, mas
   não nos relatórios mensais."
3. **Listagens:** um selo com o nome do evento ao lado da descrição. O selo precisa de
   texto, não só cor, para ser acessível.
4. **Página do evento:** total gasto, orçamento e saldo restante, gastos por categoria e a
   lista das compras. É aqui que fica o "controle" da viagem.
5. **Horizonte de Saldos:** nada muda. O saldo cai os ~R$ 11 mil como deve cair.

## 6. Testes que travam a regra

- Lançar despesa realizada de evento `fora_dos_relatorios=True`: **o saldo cai**
  (`saldo_liquidez_ate`) e **o total do mês não muda** (`totals_for_range_*`).
- Mesmo cenário com `fora_dos_relatorios=False`: entra nos dois.
- Compra de cartão no evento: fatura cheia no saldo, fatura abatida nos totais e em
  `despesas_por_categoria`.
- Custo médio do Plano de Metas não muda com o gasto do evento.
- Apagar evento com lançamentos: a exclusão é recusada (`PROTECT`).
- Backup → restore preserva `Conta.evento`, e backup antigo sem o campo restaura sem erro.
- Isolamento multi-tenant: o usuário não vincula lançamento a evento de outro usuário (validar
  no serializer).

## 7. Fases sugeridas

1. **Backend:** modelo, migration, `do_orcamento()` aplicado nos pontos da seção 4.3,
   testes da seção 6 e backup/restore.
2. **Interface mínima:** seletor de evento nos formulários, selo nas listagens e linha
   "fora do orçamento" no Dashboard.
3. **Página do evento:** orçamento e realizado, categorias, lista de compras.
4. **Cartão:** abatimento da fatura nos relatórios (seção 4.4). Sobe para a fase 1 se a
   viagem teve compras no cartão.
5. **Documentação:** `docs/eventos.md` com a regra definitiva, substituindo esta proposta.

Com as fases 1 e 2 prontas, os ~R$ 11 mil da viagem já podem ser lançados nas datas reais.

## 8. Decisões em aberto

- **Modelo:** opção C (Evento) ou algo mais enxuto (A ou B)?
- **Cartão:** a viagem teve compras no cartão? Isso define se a fase 4 entra já.
- **Relatório PDF:** listar os lançamentos de evento nas movimentações (marcados) ou
  omiti-los?
- **Receitas:** um evento pode ter receita (reembolso de uma compra, por exemplo)? Se
  puder, a mesma regra vale para `tipo=R`.
