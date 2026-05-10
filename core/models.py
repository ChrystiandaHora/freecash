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
    cartao = models.ForeignKey(
        "core.CartaoCredito",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="despesas",
    )

    # Data da compra (para despesas de cartão - diferente da data de vencimento)
    data_compra = models.DateField(null=True, blank=True, db_index=True)

    # Sistema de Fatura de Cartão
    eh_fatura_cartao = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marca se este registro é uma fatura de cartão (não uma despesa individual)",
    )

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


class CartaoCredito(AuditoriaModel):
    """
    Cartão de crédito do usuário.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cartoes",
    )

    BANDEIRA_CHOICES = (
        ("VISA", "Visa"),
        ("MASTERCARD", "Mastercard"),
        ("ELO", "Elo"),
        ("AMEX", "American Express"),
        ("HIPERCARD", "Hipercard"),
        ("DINERS", "Diners Club"),
        ("OUTRO", "Outro"),
    )

    nome = models.CharField(max_length=100)  # Ex: "Nubank", "Inter", "C6"
    bandeira = models.CharField(max_length=20, choices=BANDEIRA_CHOICES, default="VISA")
    ultimos_digitos = models.CharField(max_length=4, blank=True)
    limite = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    dia_fechamento = models.IntegerField(default=1)  # Dia que fecha a fatura
    dia_vencimento = models.IntegerField(default=10)  # Dia que vence a fatura
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Cartão de Crédito"
        verbose_name_plural = "Cartões de Crédito"

    def __str__(self):
        digitos = f" ****{self.ultimos_digitos}" if self.ultimos_digitos else ""
        return f"{self.nome}{digitos}"


class ExtratoImportado(AuditoriaModel):
    """
    Registro de um arquivo de extrato bancário importado.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="extratos_importados",
    )

    BANCO_CHOICES = (
        ("nubank", "Nubank"),
        ("inter", "Banco Inter"),
        ("itau", "Itaú"),
        ("bradesco", "Bradesco"),
        ("bb", "Banco do Brasil"),
        ("caixa", "Caixa Econômica"),
        ("santander", "Santander"),
        ("generico", "Genérico"),
    )

    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("processado", "Processado"),
        ("erro", "Erro"),
    )

    arquivo_nome = models.CharField(max_length=255)
    banco = models.CharField(max_length=20, choices=BANCO_CHOICES, default="generico")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    linhas_encontradas = models.IntegerField(default=0)
    linhas_importadas = models.IntegerField(default=0)
    erro_mensagem = models.TextField(blank=True)
    cartao = models.ForeignKey(
        "core.CartaoCredito",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extratos",
        help_text="Cartão de crédito associado a este extrato (opcional)",
    )

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "Extrato Importado"
        verbose_name_plural = "Extratos Importados"

    def __str__(self):
        return f"{self.get_banco_display()} - {self.arquivo_nome}"


class LinhaExtrato(AuditoriaModel):
    """
    Linha individual extraída de um extrato bancário.
    """

    extrato = models.ForeignKey(
        ExtratoImportado,
        on_delete=models.CASCADE,
        related_name="linhas",
    )

    TIPO_CREDITO = "C"
    TIPO_DEBITO = "D"
    TIPO_CHOICES = (
        (TIPO_CREDITO, "Crédito"),
        (TIPO_DEBITO, "Débito"),
    )

    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("importado", "Importado"),
        ("ignorado", "Ignorado"),
    )

    data = models.DateField()
    descricao = models.CharField(max_length=500)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    conta_vinculada = models.ForeignKey(
        Conta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linhas_extrato",
    )

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Linha de Extrato"
        verbose_name_plural = "Linhas de Extrato"

    def __str__(self):
        return f"{self.data} - {self.descricao[:30]} - R$ {self.valor}"
