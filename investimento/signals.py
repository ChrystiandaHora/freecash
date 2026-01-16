from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Transacao
from .services import recalcular_ativo


@receiver(post_save, sender=Transacao)
@receiver(post_delete, sender=Transacao)
def atualizar_ativo_apos_transacao(sender, instance, **kwargs):
    if instance.ativo:
        recalcular_ativo(instance.ativo)
