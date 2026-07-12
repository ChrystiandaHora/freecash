"""Sinais (Signals) do módulo Core.

Responsabilidades:
  1. Atualizar ConfigUsuario sempre que Contas ou Categorias são alteradas.
  2. Consolidar automaticamente faturas de cartão de crédito (Conta com eh_fatura_cartao=True)
     sempre que uma compra individual de cartão é criada, atualizada ou deletada.
     - Ao criar/atualizar: obtém ou cria a fatura do mês correspondente e recalcula seu valor.
     - Ao deletar: recalcula o valor da fatura (ou a remove se ficou zerada sem compras).
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import Conta, Categoria, ConfigUsuario


# ─────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────

def atualizar_config(usuario):
    """Registra o timestamp da última modificação nas configurações do usuário."""
    config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
    config.save(update_fields=["atualizada_em"])


def _consolidar_fatura(conta: Conta) -> None:
    """Obtém ou cria a fatura consolidada e recalcula seu valor total.

    Esta função é idempotente: pode ser chamada múltiplas vezes sem efeitos colaterais.
    Ela respeita o estado de liquidação da fatura (não modifica faturas já pagas).

    Args:
        conta: A compra individual de cartão que disparou a consolidação.
    """
    from core.services.fatura_service import obter_ou_criar_fatura, atualizar_valor_fatura

    # Só age em compras individuais de cartão (não nas próprias faturas consolidadas)
    if not conta.cartao or conta.eh_fatura_cartao:
        return

    if not conta.data_prevista:
        return

    fatura = obter_ou_criar_fatura(
        usuario=conta.usuario,
        cartao=conta.cartao,
        data_vencimento=conta.data_prevista,
    )
    if not fatura.categoria_id and conta.categoria_id:
        fatura.categoria = conta.categoria
        fatura.save(update_fields=["categoria", "atualizada_em"])
    atualizar_valor_fatura(fatura)


def _reconsolidar_apos_exclusao(conta: Conta) -> None:
    """Recalcula a fatura após a exclusão de uma compra individual.

    Se a fatura ficar com valor zero e não estiver paga, ela é removida
    automaticamente para não poluir a tela de Contas a Pagar.

    Args:
        conta: A compra individual de cartão que foi deletada.
    """
    from decimal import Decimal
    from core.services.fatura_service import atualizar_valor_fatura

    if not conta.cartao or conta.eh_fatura_cartao:
        return

    if not conta.data_prevista:
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

    # Remove a fatura consolidada vazia e não liquidada para manter a tela limpa
    fatura.refresh_from_db()
    if fatura.valor == Decimal("0.00") and not fatura.transacao_realizada:
        fatura.delete()
        return


# ─────────────────────────────────────────────────────────────
# Receivers
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=Conta)
def monitorar_salvamento_conta(sender, instance, **kwargs):
    """Reage ao salvamento de qualquer Conta.

    - Atualiza o timestamp de configuração do usuário.
    - Se for uma compra individual de cartão: consolida a fatura do período.
    """
    if instance.usuario_id:
        atualizar_config(instance.usuario)

    # Evitar loop infinito: _consolidar_fatura salva a fatura com update_fields,
    # o que aciona este signal novamente — mas a fatura tem eh_fatura_cartao=True,
    # logo a guarda abaixo impede a recursão.
    if not instance.eh_fatura_cartao:
        _consolidar_fatura(instance)


@receiver(post_save, sender=Categoria)
def monitorar_salvamento_categoria(sender, instance, **kwargs):
    """Atualiza o timestamp de configuração do usuário ao salvar uma categoria."""
    if instance.usuario_id:
        atualizar_config(instance.usuario)


@receiver(post_delete, sender=Conta)
def monitorar_delecao_conta(sender, instance, **kwargs):
    """Reage à exclusão de qualquer Conta.

    - Atualiza o timestamp de configuração do usuário.
    - Se for uma compra individual de cartão: reconsolida a fatura do período
      e a remove se ficar vazia.
    """
    if instance.usuario_id:
        atualizar_config(instance.usuario)

    if not instance.eh_fatura_cartao:
        _reconsolidar_apos_exclusao(instance)


@receiver(post_delete, sender=Categoria)
def monitorar_delecao_categoria(sender, instance, **kwargs):
    """Atualiza o timestamp de configuração do usuário ao deletar uma categoria."""
    if instance.usuario_id:
        atualizar_config(instance.usuario)
