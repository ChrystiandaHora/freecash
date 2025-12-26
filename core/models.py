from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


# Create your models here.
class Categoria(models.Model):
    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_INVESTIMENTO = "I"

    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_INVESTIMENTO, "Investimento"),
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categorias"
    )

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    is_default = models.BooleanField(default=False)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class FormaPagamento(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="formas_pagamento",
    )

    nome = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "nome")

    def __str__(self):
        return self.nome


class Transacao(models.Model):
    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_INVESTIMENTO = "I"

    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_INVESTIMENTO, "Investimento"),
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transacoes"
    )

    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    data = models.DateField()
    descricao = models.CharField(max_length=255, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transacoes",
    )

    forma_pagamento = models.ForeignKey(
        FormaPagamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transacoes",
    )

    # Importações antigas
    is_legacy = models.BooleanField(default=False)
    origem_ano = models.IntegerField(null=True, blank=True)
    origem_mes = models.IntegerField(null=True, blank=True)
    origem_linha = models.CharField(max_length=50, null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]

    def __str__(self):
        tipo = "Receita" if self.tipo == self.TIPO_RECEITA else "Despesa"
        return f"{tipo} - {self.valor} em {self.data}"


class ContaPagar(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_PAGO = "pago"
    STATUS_ATRASADO = "atrasado"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_PAGO, "Pago"),
        (STATUS_ATRASADO, "Atrasado"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contas_pagar"
    )

    descricao = models.CharField(max_length=255)

    valor = models.DecimalField(max_digits=12, decimal_places=2)

    data_vencimento = models.DateField()

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDENTE
    )

    categoria = models.ForeignKey(
        Categoria,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contas_pagar",
    )

    forma_pagamento = models.ForeignKey(
        FormaPagamento,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contas_pagar",
    )

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data_vencimento", "descricao"]
        verbose_name = "Conta a pagar"
        verbose_name_plural = "Contas a pagar"

    def __str__(self):
        return f"{self.descricao} - {self.valor} (vence em {self.data_vencimento})"

    @property
    def esta_pendente(self):
        return self.status == self.STATUS_PENDENTE

    @property
    def esta_paga(self):
        return self.status == self.STATUS_PAGO

    @property
    def esta_atrasada(self):
        return self.status == self.STATUS_ATRASADO


class ResumoMensal(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resumos_mensais",
    )

    ano = models.IntegerField()
    mes = models.PositiveSmallIntegerField()

    receita = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outras_receitas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_legacy = models.BooleanField(default=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "ano", "mes")
        ordering = ["-ano", "-mes"]

    def __str__(self):
        return f"{self.mes:02d}/{self.ano} → {self.total}"


class ConfigUsuario(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config"
    )

    moeda_padrao = models.CharField(max_length=10, default="BRL")
    ultimo_export_em = models.DateTimeField(null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Configurações de {self.usuario.username}"


class LogImportacao(models.Model):
    TIPO_BACKUP = "backup"
    TIPO_LEGADO = "legado"

    TIPOS = [
        (TIPO_BACKUP, "Backup Moderno"),
        (TIPO_LEGADO, "Planilha Legado"),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    sucesso = models.BooleanField(default=False)
    mensagem = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo} - {'OK' if self.sucesso else 'ERRO'}"
