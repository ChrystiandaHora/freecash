from django.db import models
from django.conf import settings


class AuditoriaMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name="Criado Por",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_modified",
        verbose_name="Modificado Por",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        abstract = True


class ClasseAtivo(AuditoriaMixin):
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


class Ativo(AuditoriaMixin):
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

    class Meta:
        unique_together = ("usuario", "ticker")
        ordering = ["ticker"]

    def __str__(self):
        return self.ticker
