from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import Conta, Categoria, FormaPagamento, ConfigUsuario

MODELOS_MONITORADOS = (Conta, Categoria, FormaPagamento)


def atualizar_config(usuario):
    config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
    config.save(update_fields=["atualizada_em"])


@receiver(post_save)
def monitorar_salvamento(sender, instance, **kwargs):
    if sender in MODELOS_MONITORADOS and getattr(instance, "usuario_id", None):
        atualizar_config(instance.usuario)


@receiver(post_delete)
def monitorar_delecao(sender, instance, **kwargs):
    if sender in MODELOS_MONITORADOS and getattr(instance, "usuario_id", None):
        atualizar_config(instance.usuario)
