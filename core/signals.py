from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import Conta, Categoria, FormaPagamento, ConfigUsuario


def atualizar_config(usuario):
    config, _ = ConfigUsuario.objects.get_or_create(created_by=usuario)
    config.save(update_fields=["updated_at"])


@receiver(post_save, sender=Conta)
@receiver(post_save, sender=Categoria)
@receiver(post_save, sender=FormaPagamento)
def monitorar_salvamento(sender, instance, **kwargs):
    if instance.created_by_id:
        atualizar_config(instance.created_by)


@receiver(post_delete, sender=Conta)
@receiver(post_delete, sender=Categoria)
@receiver(post_delete, sender=FormaPagamento)
def monitorar_delecao(sender, instance, **kwargs):
    if instance.created_by_id:
        atualizar_config(instance.created_by)
