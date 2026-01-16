from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import Conta, Categoria, FormaPagamento, ConfigUsuario


def atualizar_config(usuario):
    config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
    config.save(update_fields=["atualizada_em"])


@receiver(post_save, sender=Conta)
@receiver(post_save, sender=Categoria)
@receiver(post_save, sender=FormaPagamento)
def monitorar_salvamento(sender, instance, **kwargs):
    if instance.usuario_id:
        atualizar_config(instance.usuario)


@receiver(post_delete, sender=Conta)
@receiver(post_delete, sender=Categoria)
@receiver(post_delete, sender=FormaPagamento)
def monitorar_delecao(sender, instance, **kwargs):
    if instance.usuario_id:
        atualizar_config(instance.usuario)
