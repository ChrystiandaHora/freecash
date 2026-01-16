from django.db import models
from django.conf import settings
from core.models import AuditoriaModel


class ClasseAtivo(AuditoriaModel):
    """
    Nível 1: Renda Fixa, Renda Variável, Multimercado, Cambial, etc.
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
        return self.nome


class CategoriaAtivo(AuditoriaModel):
    """
    Nível 2: Indexado, Pré-fixado, Ações, FII, etc.
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
        return f"{self.nome} ({self.classe.nome})"


class SubcategoriaAtivo(AuditoriaModel):
    """
    Nível 3: Soberano, Crédito Privado, Tijolo, Papel, etc.
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
        return f"{self.categoria.classe.nome} > {self.categoria.nome} > {self.nome}"


class Ativo(AuditoriaModel):
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

    # Campos calculados / Cache
    quantidade = models.DecimalField(max_digits=19, decimal_places=8, default=0)
    preco_medio = models.DecimalField(max_digits=19, decimal_places=4, default=0)

    class Meta:
        unique_together = ("usuario", "ticker")
        ordering = ["ticker"]

    def __str__(self):
        return f"{self.ticker} ({self.quantidade})"


class Transacao(AuditoriaModel):
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
        return f"{self.get_tipo_display()} {self.ativo.ticker} - {self.data}"
