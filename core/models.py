from django.utils import timezone
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


# Create your models here.
import uuid


class AuditoriaModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Categoria(AuditoriaModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categorias",
    )

    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_INVESTIMENTO = "I"

    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_INVESTIMENTO, "Investimento"),
    )

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class FormaPagamento(AuditoriaModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="formas_pagamento",
    )

    nome = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("usuario", "nome")

    def __str__(self):
        return self.nome


class Conta(AuditoriaModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contas",
    )

    # Natureza
    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_INVESTIMENTO = "I"
    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_INVESTIMENTO, "Investimento"),
    )

    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=255, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    eh_parcelada = models.BooleanField(default=False, db_index=True)
    parcela_numero = models.IntegerField(null=True, blank=True)
    parcela_total = models.IntegerField(null=True, blank=True)
    grupo_parcelamento = models.IntegerField(null=True, blank=True, db_index=True)

    # Agendamento (equivale ao vencimento / data prevista)
    data_prevista = models.DateField(db_index=True)

    # Realização (equivale a “virou transação”)
    transacao_realizada = models.BooleanField(default=False, db_index=True)
    data_realizacao = models.DateField(null=True, blank=True, db_index=True)

    categoria = models.ForeignKey(
        "core.Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas",
    )
    forma_pagamento = models.ForeignKey(
        "core.FormaPagamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas",
    )

    # (Opcional) para manter importações antigas
    is_legacy = models.BooleanField(default=False)
    origem_ano = models.IntegerField(null=True, blank=True)
    origem_mes = models.IntegerField(null=True, blank=True)
    origem_linha = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ["-data_prevista", "-id"]
        indexes = [
            models.Index(fields=["usuario", "tipo", "data_prevista"]),
            models.Index(fields=["usuario", "transacao_realizada", "data_realizacao"]),
        ]

    def __str__(self):
        status = "Realizada" if self.transacao_realizada else "Prevista"
        return (
            f"{status} {self.get_tipo_display()} - {self.valor} ({self.data_prevista})"
        )

    @property
    def esta_atrasada(self):
        # Atrasada = passou da data prevista e ainda não foi realizada
        return (not self.transacao_realizada) and (
            self.data_prevista < timezone.localdate()
        )

    def marcar_realizada(self, data=None):
        if self.transacao_realizada:
            return
        self.transacao_realizada = True
        self.data_realizacao = data or timezone.localdate()
        self.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

    def desmarcar_realizada(self):
        self.transacao_realizada = False
        self.data_realizacao = None
        self.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )


class ConfigUsuario(AuditoriaModel):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config"
    )
    moeda_padrao = models.CharField(max_length=10, default="BRL")
    ultimo_export_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Configurações de {self.usuario.username}"
