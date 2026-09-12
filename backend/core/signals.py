"""Signals do módulo Core para atualização de ConfigUsuario e consolidação de faturas de cartão."""

from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Categoria, ConfigUsuario, Conta


def atualizar_config(usuario):
    """Atualiza o timestamp da última modificação nas configurações do usuário."""
    config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
    config.save(update_fields=["atualizada_em"])


def atualizar_config_existente(usuario):
    """Atualiza o timestamp apenas se a configuração ainda existir (evita recriar no cascade de delete)."""
    ConfigUsuario.objects.filter(usuario=usuario).update(
        atualizada_em=timezone.now()
    )


def _consolidar_fatura(conta: Conta) -> None:
    """Consolida e recalcula a fatura do cartão referente ao lançamento."""
    from core.services.fatura_service import (
        atualizar_valor_fatura,
        garantir_categoria_cartao,
        obter_ou_criar_fatura,
    )

    if not conta.cartao or conta.eh_fatura_cartao or not conta.data_prevista:
        return

    fatura = obter_ou_criar_fatura(
        usuario=conta.usuario,
        cartao=conta.cartao,
        data_vencimento=conta.data_prevista,
    )
    garantir_categoria_cartao(fatura)
    atualizar_valor_fatura(fatura)


def _reconsolidar_apos_exclusao(conta: Conta) -> None:
    """Recalcula a fatura após exclusão de uma compra; remove a fatura se ficar zerada."""
    from core.services.fatura_service import atualizar_valor_fatura

    if not conta.cartao or conta.eh_fatura_cartao or not conta.data_prevista:
        return

    fatura = Conta.objects.filter(
        usuario=conta.usuario,
        cartao=conta.cartao,
        eh_fatura_cartao=True,
        data_prevista__year=conta.data_prevista.year,
        data_prevista__month=conta.data_prevista.month,
    ).first()

    if not fatura:
        return

    atualizar_valor_fatura(fatura)
    fatura.refresh_from_db()
    if fatura.valor == Decimal("0.00") and not fatura.transacao_realizada:
        fatura.delete()


@receiver(post_save, sender=Conta)
def monitorar_salvamento_conta(sender, instance, **kwargs):
    """Atualiza config do usuário e consolida fatura se for compra de cartão."""
    if instance.usuario_id:
        atualizar_config(instance.usuario)

    if not instance.eh_fatura_cartao:
        _consolidar_fatura(instance)


@receiver(post_save, sender=Categoria)
def monitorar_salvamento_categoria(sender, instance, **kwargs):
    """Atualiza config do usuário ao salvar categoria."""
    if instance.usuario_id:
        atualizar_config(instance.usuario)


@receiver(post_delete, sender=Conta)
def monitorar_delecao_conta(sender, instance, **kwargs):
    """Atualiza config e reconsolida faturas ao excluir conta."""
    if instance.usuario_id:
        atualizar_config_existente(instance.usuario)

    if not instance.eh_fatura_cartao:
        _reconsolidar_apos_exclusao(instance)


@receiver(post_delete, sender=Categoria)
def monitorar_delecao_categoria(sender, instance, **kwargs):
    """Atualiza config existente ao excluir categoria."""
    if instance.usuario_id:
        atualizar_config_existente(instance.usuario)

