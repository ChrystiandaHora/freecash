from django.db import models
from django.conf import settings
from core.models import AuditoriaModel


class ClasseAtivo(AuditoriaModel):
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

    def __str__(self):
        return self.nome


class Ativo(AuditoriaModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ativos",
    )

    ticker = models.CharField(max_length=20)
    nome = models.CharField(max_length=120, blank=True)

    classe = models.ForeignKey(
        ClasseAtivo,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ativos",
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
