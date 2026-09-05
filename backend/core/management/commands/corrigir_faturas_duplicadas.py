"""Comando Customizado do Django para Deduplicação de Faturas de Cartão.

É o comando citado pelo aviso que `obter_ou_criar_fatura` emite ao encontrar mais de
uma fatura consolidada no mesmo ciclo. Duplicatas surgem tipicamente ao restaurar
backup de uma versão que criava faturas fantasma no import.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.services.fatura_service import deduplicar_faturas


class Command(BaseCommand):
    """Classe executora da deduplicação de faturas consolidadas de cartão."""

    help = (
        "Remove faturas de cartão duplicadas no mesmo mês, preservando a liquidada "
        "e reatribuindo as compras das removidas."
    )

    def add_arguments(self, parser):
        """Declara as opções aceitas pelo comando."""
        parser.add_argument(
            "--usuario",
            dest="usuario",
            default=None,
            help="Restringe a limpeza ao username informado (padrão: todos).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas relata o que seria removido, sem gravar nada.",
        )

    def handle(self, *args, **options):
        """Executa a deduplicação e imprime um resumo por período afetado."""
        dry_run = options["dry_run"]
        usuario = None

        if options["usuario"]:
            usuario = get_user_model().objects.filter(
                username=options["usuario"]
            ).first()
            if usuario is None:
                self.stdout.write(
                    self.style.ERROR(f'Usuário "{options["usuario"]}" não encontrado.')
                )
                return

        relatorio = deduplicar_faturas(usuario=usuario, dry_run=dry_run)

        if not relatorio:
            self.stdout.write(self.style.SUCCESS("Nenhuma fatura duplicada encontrada."))
            return

        total_removidas = 0
        total_datas = 0

        for grupo in relatorio:
            removidas = grupo["removidas"]
            datas = grupo["datas_reatribuidas"]
            total_removidas += len(removidas)
            total_datas += len(datas)

            self.stdout.write(
                f"cartão {grupo['cartao_id']} em {grupo['mes']:02d}/{grupo['ano']}: "
                f"mantida a fatura {grupo['mantida'].id}, "
                f"removida(s) {[f.id for f in removidas]}."
            )
            if datas:
                self.stdout.write(
                    f"  compras de {', '.join(d.isoformat() for d in datas)} "
                    f"reatribuídas para {grupo['mantida'].data_prevista.isoformat()}."
                )

        prefixo = "[dry-run] Seriam removidas" if dry_run else "Removidas"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefixo} {total_removidas} fatura(s) duplicada(s) em "
                f"{len(relatorio)} período(s); {total_datas} data(s) de compra reatribuída(s)."
            )
        )
