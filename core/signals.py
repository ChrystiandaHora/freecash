from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.models import (
    Transacao,
    ContaPagar,
    Categoria,
    FormaPagamento,
    ResumoMensal,
    ConfigUsuario,
)

MODELOS_MONITORADOS = (
    Transacao,
    ContaPagar,
    Categoria,
    FormaPagamento,
    ResumoMensal,
)


def atualizar_config(usuario):
    config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
    config.save()  # Isso atualiza 'atualizada_em' automaticamente


@receiver(post_save)
def monitorar_salvamento(sender, instance, **kwargs):
    if sender in MODELOS_MONITORADOS:
        atualizar_config(instance.usuario)


@receiver(post_delete)
def monitorar_delecao(sender, instance, **kwargs):
    if sender in MODELOS_MONITORADOS:
        atualizar_config(instance.usuario)
