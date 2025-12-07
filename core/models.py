from django.db import models
from django.conf import settings


# Create your models here.
class Categoria(models.Model):
    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_AMBOS = "A"

    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_AMBOS, "Ambos"),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES, default=TIPO_AMBOS)
    ativa = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "nome")
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return f"{self.nome}"


class FormaPagamento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "nome")
        verbose_name = "Forma de pagamento"
        verbose_name_plural = "Formas de pagamento"

    def __str__(self):
        return self.nome


class Transacao(models.Model):
    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"

    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    data = models.DateField()
    descricao = models.CharField(max_length=255, blank=True)

    valor = models.DecimalField(max_digits=12, decimal_places=2)

    categoria = models.ForeignKey(
        "Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transacoes",
    )

    forma_pagamento = models.ForeignKey(
        "FormaPagamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transacoes",
    )

    # Campos para controle de origem
    is_legacy = models.BooleanField(
        default=False,
        help_text="Indica se a transacao foi gerada a partir de importacao de planilha agregada",
    )
    origem_ano = models.IntegerField(null=True, blank=True)
    origem_mes = models.IntegerField(null=True, blank=True)
    origem_linha = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Por exemplo RECEITA, OUTRAS RECEITAS, GASTOS",
    )

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transacao"
        verbose_name_plural = "Transacoes"
        ordering = ["-data", "-id"]

    def __str__(self):
        tipo = "Receita" if self.tipo == self.TIPO_RECEITA else "Despesa"
        return f"{tipo} {self.valor} em {self.data}"


class ResumoMensal(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    ano = models.IntegerField()
    mes = models.PositiveSmallIntegerField()  # 1 a 12

    receita = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outras_receitas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Indica se isto veio da planilha antiga
    is_legacy = models.BooleanField(default=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "ano", "mes")
        verbose_name = "Resumo mensal"
        verbose_name_plural = "Resumos mensais"
        ordering = ["-ano", "-mes"]

    def __str__(self):
        return f"{self.mes:02d}/{self.ano} - total {self.total}"


class ConfigUsuario(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    moeda_padrao = models.CharField(max_length=10, default="BRL")
    ultimo_export_em = models.DateTimeField(null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracao do usuario"
        verbose_name_plural = "Configuracoes do usuario"

    def __str__(self):
        return f"Config de {self.usuario}"
