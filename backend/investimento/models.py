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

    Atributos:
        usuario (User): Proprietário da classe de ativos.
        nome (str): Nome descritivo (ex: Renda Fixa).
        ativa (bool): Estado da classe.
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
    """Representa a categoria intermediária de segmentação do ativo (ex: Ações, Tesouro Direto).

    Nível 2 da hierarquia.

    Atributos:
        usuario (User): Proprietário da categoria de ativos.
        classe (ClasseAtivo): A macro classe à qual pertence.
        nome (str): Nome descritivo da categoria.
        ativa (bool): Flag de ativação.
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

    Atributos:
        usuario (User): Proprietário da subcategoria.
        categoria (CategoriaAtivo): Categoria intermediária vinculada.
        nome (str): Nome descritivo da subcategoria.
        ativa (bool): Flag de ativação.
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


class Ativo(AuditoriaModel):
    """Representa um ativo financeiro específico de Renda Fixa ou Renda Variável.

    Controla emissor, indexador, taxas, metas percentuais de balanceamento de
    carteira B3, além de caches calculados de quantidade e preço médio acumulados.

    Atributos:
        usuario (User): Proprietário do ativo custodiado.
        ticker (str): Código de negociação do ativo na bolsa (ex: PETR4).
        nome (str): Nome completo ou razão social da empresa emissora.
        subcategoria (SubcategoriaAtivo): Vínculo com a folha da segmentação de ativos.
        data_vencimento (date): Vencimento do título caso seja Renda Fixa.
        emissor (str): Banco ou empresa emissora do título.
        indexador (str): Indexador monetário da taxa (CDI, IPCA, SELIC, PRE, etc.).
        taxa (Decimal): Porcentagem ou prêmio (ex: 110 para 110% CDI ou 6.5 para IPCA+6.5%).
        moeda (str): Código monetário oficial (ex: BRL).
        ativo (bool): Flag de custódia ativa.
        meta_porcentagem (Decimal): Meta percentual de alocação no portfólio.
        quantidade (Decimal): Quantidade em custódia do investidor.
        preco_medio (Decimal): Preço médio de aquisição por cota/título.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ativos",
    )

    ticker = models.CharField(max_length=20)
    nome = models.CharField(max_length=120, blank=True)

    # Vínculo com a subcategoria (folha da árvore)
    subcategoria = models.ForeignKey(
        SubcategoriaAtivo,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ativos",
    )

    # Detalhes Renda Fixa (ANBIMA Standard)
    INDEXADOR_CHOICES = (
        ("CDI", "CDI"),
        ("IPCA", "IPCA"),
        ("SELIC", "SELIC"),
        ("PRE", "Pré-fixado"),
        ("IGPM", "IGP-M"),
        ("OUTROS", "Outros"),
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

    moeda = models.CharField(max_length=10, default="BRL")
    ativo = models.BooleanField(default=True)
    meta_porcentagem = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Meta (%)",
        help_text="Porcentagem alvo deste ativo na carteira",
    )

    # Campos calculados / Cache
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



class Cotacao(AuditoriaModel):
    """Snapshot histórico de cotação diária de um ativo B3 a mercado.

    Atributos:
        ativo (Ativo): O ativo custodiado correspondente.
        data (date): Data de competência da cotação.
        valor (Decimal): Valor unitário de mercado do ativo na data.
    """
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
    """Representa uma ordem executada de Compra, Venda ou recebimento de Provento.

    Atributos:
        usuario (User): O investidor proprietário da ordem.
        ativo (Ativo): Ativo financeiro negociado.
        tipo (str): Tipo da operação ('C' para Compra, 'V' para Venda, 'D' para Proventos/Dividendos).
        data (date): Data física de execução da ordem.
        quantidade (Decimal): Quantidade transacionada na data.
        preco_unitario (Decimal): Preço pago ou recebido por cota/título.
        taxas (Decimal): Custos de corretagem e taxas de liquidação da B3.
        valor_total (Decimal): Valor final líquido consolidado da transação.
    """
    TIPO_COMPRA = "C"
    TIPO_VENDA = "V"
    TIPO_DIVIDENDO = "D"  # Dividendo, JCP, Rendimento

    TIPO_CHOICES = (
        (TIPO_COMPRA, "Compra"),
        (TIPO_VENDA, "Venda"),
        (TIPO_DIVIDENDO, "Provento (Dividendo/JCP)"),
    )

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

    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
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

    def __str__(self):
        """Retorna uma string com o tipo, ticker e a data de negociação.

        Returns:
            str: Mapeamento textual resumido da ordem.
        """
        return f"{self.get_tipo_display()} {self.ativo.ticker} - {self.data}"


class CarteiraHistorico(AuditoriaModel):
    """Snapshot histórico diário consolidado da carteira do investidor.

    Salva agregados de patrimônio a mercado, total de ordens e proventos,
    alimentando de forma instantânea gráficos e séries evolutivas anuais do frontend.

    Atributos:
        usuario (User): Investidor proprietário do snapshot.
        data (date): Data de apuração do snapshot.
        patrimonio (Decimal): Valor total consolidado a mercado na data.
        total_compras (Decimal): Volume de ordens de compra acumulado.
        total_vendas (Decimal): Volume de ordens de venda acumulado.
        total_dividendos (Decimal): Proventos acumulados recebidos na data.
        rentabilidade (Decimal): Lucro/Prejuízo total consolidado na data.
        rentabilidade_percentual (Decimal): Percentual de rentabilidade acumulado da carteira.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carteira_historico",
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
        unique_together = ("usuario", "data")

    def __str__(self):
        """Retorna string amigável com ID do usuário, data e valor patrimonial.

        Returns:
            str: Representação descritiva do snapshot.
        """
        return f"{self.usuario_id} - {self.data} - {self.patrimonio}"
