"""
Modelos de Banco de Dados do Módulo de Investimentos.

Representa a carteira ativa de investimentos do usuário, fornecendo classes para
dividir ativos (Renda Fixa, Renda Variável, Multimercado, Cambial), listar ativos
individuais (ex: PETR4) e registrar ordens de compra, venda e recebimento de proventos.
"""

from decimal import Decimal

from django.db import models
from django.conf import settings
from core.models import AuditoriaModel


class ClasseAtivo(AuditoriaModel):
    """Representa a classe macroeconômica do ativo (Renda Fixa, Renda Variável, etc.).

    Nível 1 da hierarquia de segmentação de ativos.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classes_ativos",
    )
    nome = models.CharField(max_length=60)
    ativa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["nome"]
        verbose_name = "Classe de Ativo"
        verbose_name_plural = "Classes de Ativos"

    def __str__(self):
        """Retorna o nome descritivo da classe.

        Returns:
            str: Nome da classe macroeconômica.
        """
        return self.nome


class CategoriaAtivo(AuditoriaModel):
    """Categoria intermediária do ativo (ex.: Ações, Tesouro Direto).

    Nível 2 da hierarquia.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categorias_ativos",
    )
    classe = models.ForeignKey(
        ClasseAtivo,
        on_delete=models.CASCADE,
        related_name="categorias",
    )
    nome = models.CharField(max_length=60)
    ativa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("usuario", "classe", "nome")
        ordering = ["nome"]
        verbose_name = "Categoria de Ativo"
        verbose_name_plural = "Categorias de Ativos"

    def __str__(self):
        """Retorna uma identificação da categoria aninhada com sua classe.

        Returns:
            str: Categoria e Classe correspondente.
        """
        return f"{self.nome} ({self.classe.nome})"


class SubcategoriaAtivo(AuditoriaModel):
    """Representa a subcategoria folha do ativo (ex: Soberano, Tijolo, Papel).

    Nível 3 da árvore hierárquica.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subcategorias_ativos",
    )
    categoria = models.ForeignKey(
        CategoriaAtivo,
        on_delete=models.CASCADE,
        related_name="subcategorias",
    )
    nome = models.CharField(max_length=60)
    ativa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("usuario", "categoria", "nome")
        ordering = ["categoria__classe__nome", "categoria__nome", "nome"]
        verbose_name = "Subcategoria de Ativo"
        verbose_name_plural = "Subcategorias de Ativos"

    def __str__(self):
        """Retorna o caminho estruturado completo do ativo.

        Returns:
            str: Caminho classe > categoria > subcategoria.
        """
        return f"{self.categoria.classe.nome} > {self.categoria.nome} > {self.nome}"


class Carteira(AuditoriaModel):
    """Uma custódia do usuário — tipicamente a conta numa corretora ou banco.

    A carteira é a **custódia**, não a definição do papel: ela fica na `Transacao`,
    e não no `Ativo`. Pendurá-la no ativo duplicaria o mesmo papel por corretora,
    e com ele a série de `Cotacao` (duas chamadas ao TradingView pelo mesmo ticker)
    e o preço médio — que no Brasil é apurado por CPF, não por instituição. Aqui, o
    ativo continua único e a posição por carteira é derivada em `PosicaoCarteira`.

    Atributos:
        considerar_no_saldo: Se o valor custodiado aqui conta como dinheiro
            disponível na projeção do Horizonte de Saldos. Uma reserva de
            emergência conta; uma posição em ações, provavelmente não.
        meta_porcentagem: Peso alvo desta carteira no patrimônio total. A meta por
            ativo mora em `PosicaoCarteira` e soma 100% *dentro* de cada carteira.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carteiras",
    )
    nome = models.CharField(max_length=80)
    instituicao = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Instituição",
        help_text="Corretora ou banco onde os ativos estão custodiados",
    )
    cor = models.CharField(max_length=7, blank=True, help_text="Cor em hexadecimal")

    meta_porcentagem = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Meta (%)",
        help_text="Porcentagem alvo desta carteira no patrimônio total",
    )
    considerar_no_saldo = models.BooleanField(
        default=True,
        verbose_name="Considerar no saldo",
        help_text="Somar o valor desta carteira ao saldo projetado no Horizonte",
    )
    ativa = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["ordem", "nome"]
        verbose_name = "Carteira"
        verbose_name_plural = "Carteiras"

    NOME_PADRAO = "Carteira Padrão"

    @classmethod
    def padrao_de(cls, usuario):
        """Devolve a custódia default do usuário, criando-a se ainda não existir.

        Toda transação precisa de carteira, então este é o ponto único que responde
        "e quando o usuário não escolheu nenhuma?" — usado pelo cadastro de ativo, e
        pela restauração de backups anteriores às carteiras.

        Returns:
            Carteira: A primeira carteira do usuário, ou uma Carteira Padrão nova.
        """
        carteira = cls.objects.filter(usuario=usuario).order_by("ordem", "id").first()
        if carteira:
            return carteira
        return cls.objects.create(
            usuario=usuario, nome=cls.NOME_PADRAO, considerar_no_saldo=True
        )

    def __str__(self):
        """Retorna o nome da carteira, com a instituição quando houver.

        Returns:
            str: Identificação da custódia.
        """
        if self.instituicao:
            return f"{self.nome} ({self.instituicao})"
        return self.nome


class Ativo(AuditoriaModel):
    """Representa um ativo financeiro específico de Renda Fixa ou Renda Variável.

    Guarda caches calculados de quantidade e preço médio **consolidados** — a soma
    de todas as carteiras, que é como o preço médio é apurado fiscalmente. A posição
    e a meta de balanceamento por carteira ficam em `PosicaoCarteira`. Atributos
    exclusivos de Renda Fixa (emissor, indexador, taxa, vencimento) ficam em
    `DetalheRendaFixa`.

    Atributos:
        preco_medio: Preço médio de aquisição por cota/título.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ativos",
    )

    ticker = models.CharField(max_length=20)
    nome = models.CharField(max_length=120, blank=True)
    cnpj = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        verbose_name="CNPJ do Fundo",
        help_text="Somente números (14 dígitos) para atualização via CVM",
    )

    # Vínculo com a subcategoria (folha da árvore)
    subcategoria = models.ForeignKey(
        SubcategoriaAtivo,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ativos",
    )

    moeda = models.CharField(max_length=10, default="BRL")
    ativo = models.BooleanField(default=True)

    # Campos calculados / Cache (consolidado de todas as carteiras)
    quantidade = models.DecimalField(max_digits=19, decimal_places=8, default=0)
    preco_medio = models.DecimalField(max_digits=19, decimal_places=4, default=0)

    class Meta:
        unique_together = ("usuario", "ticker")
        ordering = ["ticker"]

    @property
    def valor_total(self) -> Decimal:
        """Calcula o valor total investido com base no preço médio.

        Returns:
            Decimal: Total investido acumulado.
        """
        return self.quantidade * self.preco_medio

    def __str__(self):
        """Retorna uma string contendo ticker e quantidade custodiada.

        Returns:
            str: Resumo textual do ativo.
        """
        return f"{self.ticker} ({self.quantidade})"

    @property
    def valor_investido(self) -> Decimal:
        """Retorna o valor total pago/investido de aquisição histórica.

        Returns:
            Decimal: Total investido (aquisição).
        """
        return self.quantidade * self.preco_medio

    @property
    def cotacao_atual(self) -> Decimal | None:
        """Obtém a cotação mais recente cadastrada para este ativo.

        Returns:
            Decimal | None: Valor da cotação ou None se não houver registros históricos.
        """
        ultima = self.cotacoes.order_by("-data", "-criada_em").first()
        if ultima:
            return ultima.valor
        return None

    @property
    def valor_total_atual(self) -> Decimal:
        """Calcula o valor atual da posição na carteira a mercado.

        Utiliza a cotação atualizada mais recente, caindo para o preço médio
        como fallback conservador.

        Returns:
            Decimal: Valor de mercado da posição.
        """
        ultima = self.cotacoes.order_by("-data", "-criada_em").first()
        if ultima:
            return self.quantidade * ultima.valor
        return self.valor_investido

    @property
    def rentabilidade(self) -> Decimal:
        """Calcula o ganho de capital absoluto (lucro ou prejuízo não realizado).

        Returns:
            Decimal: Valor da diferença absoluta.
        """
        return self.valor_total_atual - self.valor_investido

    @property
    def rentabilidade_percentual(self) -> Decimal:
        """Calcula a rentabilidade percentual acumulada da posição.

        Returns:
            Decimal: A taxa percentual de ganho/perda de capital.
        """
        if self.valor_investido == 0:
            return Decimal(0)
        return (self.rentabilidade / self.valor_investido) * 100

    def save(self, *args, **kwargs):
        """Normaliza o CNPJ removendo pontuações antes de salvar."""
        if self.cnpj:
            self.cnpj = "".join(filter(str.isdigit, self.cnpj))
        super().save(*args, **kwargs)


class DetalheRendaFixa(AuditoriaModel):
    """Atributos contratuais exclusivos de ativos de Renda Fixa/Dívida (ANBIMA Standard).

    Extraído de `Ativo` porque só se aplica a um subconjunto de ativos
    (renda fixa/alternativos) — mantendo `Ativo` livre de colunas sempre
    vazias para ações, FIIs e fundos.
    """

    INDEXADOR_CHOICES = (
        ("CDI", "CDI"),
        ("IPCA", "IPCA"),
        ("SELIC", "SELIC"),
        ("PRE", "Pré-fixado"),
        ("IGPM", "IGP-M"),
        ("OUTROS", "Outros"),
    )

    ativo = models.OneToOneField(
        Ativo,
        on_delete=models.CASCADE,
        related_name="detalhe_renda_fixa",
    )
    data_vencimento = models.DateField(
        null=True, blank=True, verbose_name="Data de Vencimento"
    )
    emissor = models.CharField(
        max_length=100, blank=True, verbose_name="Emissor (Banco/Empresa)"
    )
    indexador = models.CharField(
        max_length=10, choices=INDEXADOR_CHOICES, blank=True, verbose_name="Indexador"
    )
    taxa = models.DecimalField(
        max_digits=9,
        decimal_places=4,
        default=0,
        help_text="Ex: 100 para 100% do CDI ou 6.5 para IPCA+6.5%",
        verbose_name="Taxa / Porcentagem",
    )

    class Meta:
        verbose_name = "Detalhe de Renda Fixa"
        verbose_name_plural = "Detalhes de Renda Fixa"

    def __str__(self):
        return f"Renda Fixa de {self.ativo.ticker}"



class Cotacao(AuditoriaModel):
    """Snapshot histórico de cotação diária de um ativo B3 a mercado."""
    ativo = models.ForeignKey(
        Ativo,
        on_delete=models.CASCADE,
        related_name="cotacoes",
    )
    data = models.DateField()
    valor = models.DecimalField(max_digits=19, decimal_places=4)

    class Meta:
        ordering = ["-data", "-criada_em"]
        unique_together = ("ativo", "data")

    def __str__(self):
        """Retorna resumo amigável contendo ticker, data e valor da cotação.

        Returns:
            str: Representação descritiva da cotação.
        """
        return f"{self.ativo.ticker} - {self.data} - {self.valor}"


class Transacao(AuditoriaModel):
    """Representa uma ordem executada de Compra, Venda, Provento ou Transferência.

    A transferência entre carteiras existe como tipo próprio, em duas pernas ligadas
    por `grupo_transferencia`, porque registrá-la como venda + compra falsearia o
    preço médio, a rentabilidade e o histórico de proventos: mudar de corretora não
    é realizar lucro.

    Atributos:
        usuario: O investidor proprietário da ordem.
        tipo: Tipo da operação ('C' Compra, 'V' Venda, 'D' Provento,
            'TS'/'TE' saída e entrada de transferência entre carteiras).
        carteira: A custódia em que a ordem foi executada.
        data: Data física de execução da ordem.
        preco_unitario: Preço pago ou recebido por cota/título.
    """
    TIPO_COMPRA = "C"
    TIPO_VENDA = "V"
    TIPO_DIVIDENDO = "D"  # Dividendo, JCP, Rendimento
    TIPO_TRANSF_SAIDA = "TS"
    TIPO_TRANSF_ENTRADA = "TE"

    TIPO_CHOICES = (
        (TIPO_COMPRA, "Compra"),
        (TIPO_VENDA, "Venda"),
        (TIPO_DIVIDENDO, "Provento (Dividendo/JCP)"),
        (TIPO_TRANSF_SAIDA, "Transferência (saída)"),
        (TIPO_TRANSF_ENTRADA, "Transferência (entrada)"),
    )

    # Tipos que movem custódia sem alterar a posição consolidada do usuário.
    TIPOS_TRANSFERENCIA = (TIPO_TRANSF_SAIDA, TIPO_TRANSF_ENTRADA)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transacoes_investimento",
    )
    ativo = models.ForeignKey(
        Ativo,
        on_delete=models.CASCADE,
        related_name="transacoes",
    )
    # CASCADE, não PROTECT: a guarda é de negócio e vive em `CarteiraViewSet.destroy`.
    # No schema, o PROTECT quebrava a exclusão de conta (ver docs/carteiras.md).
    carteira = models.ForeignKey(
        Carteira,
        on_delete=models.CASCADE,
        related_name="transacoes",
    )

    # As duas pernas de uma transferência compartilham este identificador, para que
    # apagar uma apague a outra — meia transferência inventaria ou sumiria com cotas.
    grupo_transferencia = models.UUIDField(null=True, blank=True, db_index=True)

    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES)
    data = models.DateField()

    # Quantidade negociada (positivo para compra, negativo para venda interna, mas aqui armazenamos absoluto e o tipo define)
    quantidade = models.DecimalField(max_digits=19, decimal_places=8)

    # Preço unitário (para compra/venda)
    preco_unitario = models.DecimalField(max_digits=19, decimal_places=4, default=0)

    # Taxas / Corretagem (opcional)
    taxas = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Valor Total = (qtd * preco) + taxas (se compra) ou - taxas (se venda)
    valor_total = models.DecimalField(max_digits=19, decimal_places=2)

    class Meta:
        ordering = ["-data", "-criada_em"]
        indexes = [
            models.Index(
                fields=["usuario", "carteira"], name="idx_transacao_usuario_carteira"
            ),
        ]

    def __str__(self):
        """Retorna uma string com o tipo, ticker e a data de negociação.

        Returns:
            str: Mapeamento textual resumido da ordem.
        """
        return f"{self.get_tipo_display()} {self.ativo.ticker} - {self.data}"


class PosicaoCarteira(AuditoriaModel):
    """Posição de um ativo dentro de uma carteira, e a meta de alocação nela.

    Os campos de quantidade e custo são **cache**, recalculados a partir das
    transações — o mesmo padrão de `Ativo.quantidade`/`preco_medio`, replicado por
    carteira. `meta_porcentagem`, ao contrário, é intenção declarada pelo usuário.

    As duas coisas moram na mesma linha, e por isso a linha **nunca é apagada**: se
    zerar a posição a removesse, a meta configurada sumiria em silêncio junto. O
    recálculo escreve apenas os campos de cache, com `update_fields`.

    Atributos:
        custo_total: Custo de aquisição remanescente nesta custódia.
        meta_porcentagem: Alvo deste ativo *dentro* desta carteira; soma 100% por carteira.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posicoes_carteira",
    )
    carteira = models.ForeignKey(
        Carteira,
        on_delete=models.CASCADE,
        related_name="posicoes",
    )
    ativo = models.ForeignKey(
        Ativo,
        on_delete=models.CASCADE,
        related_name="posicoes",
    )

    # Cache recalculado por `recalcular_posicoes_do_ativo`
    quantidade = models.DecimalField(max_digits=19, decimal_places=8, default=0)
    custo_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    preco_medio = models.DecimalField(max_digits=19, decimal_places=4, default=0)

    # Intenção do usuário — nunca tocada pelo recálculo
    meta_porcentagem = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Meta (%)",
        help_text="Porcentagem alvo deste ativo dentro desta carteira",
    )

    class Meta:
        unique_together = ("carteira", "ativo")
        ordering = ["carteira__ordem", "carteira__nome", "ativo__ticker"]
        verbose_name = "Posição em Carteira"
        verbose_name_plural = "Posições em Carteira"

    @property
    def valor_investido(self) -> Decimal:
        """Retorna o custo de aquisição da posição nesta carteira.

        Returns:
            Decimal: Custo remanescente em custódia.
        """
        return self.quantidade * self.preco_medio

    @property
    def valor_total_atual(self) -> Decimal:
        """Calcula o valor de mercado da posição nesta carteira.

        Usa a cotação do ativo, que é única por ticker — a carteira não muda o preço
        de mercado do papel, só onde ele está guardado.

        Returns:
            Decimal: Valor a mercado, caindo para o custo quando não há cotação.
        """
        cotacao = self.ativo.cotacao_atual
        if cotacao is not None:
            return self.quantidade * cotacao
        return self.valor_investido

    def __str__(self):
        """Retorna o ativo, a carteira e a quantidade custodiada.

        Returns:
            str: Resumo textual da posição.
        """
        return f"{self.ativo.ticker} em {self.carteira.nome} ({self.quantidade})"


class CarteiraHistorico(AuditoriaModel):
    """Snapshot histórico diário do patrimônio, por carteira.

    Salva agregados de patrimônio a mercado, total de ordens e proventos,
    alimentando de forma instantânea gráficos e séries evolutivas anuais do frontend.

    O snapshot é **sempre de uma carteira**; o consolidado é agregação SQL sobre estas
    linhas, e não uma linha com `carteira` nulo. Uma linha "consolidada" seria uma
    segunda fonte de verdade para o mesmo número — e, como o Postgres trata NULLs como
    distintos entre si, a `unique_together` não impediria duplicá-la.

    Atributos:
        rentabilidade: Lucro/Prejuízo consolidado da carteira na data.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carteira_historico",
    )
    carteira = models.ForeignKey(
        Carteira,
        on_delete=models.CASCADE,
        related_name="historico",
    )
    data = models.DateField()

    patrimonio = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total_compras = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    total_vendas = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    total_dividendos = models.DecimalField(max_digits=19, decimal_places=2, default=0)

    rentabilidade = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    rentabilidade_percentual = models.DecimalField(
        max_digits=19, decimal_places=6, default=0
    )

    class Meta:
        ordering = ["-data", "-criada_em"]
        unique_together = ("usuario", "carteira", "data")

    def __str__(self):
        """Retorna string amigável com a carteira, data e valor patrimonial.

        Returns:
            str: Representação descritiva do snapshot.
        """
        return f"{self.carteira_id} - {self.data} - {self.patrimonio}"
