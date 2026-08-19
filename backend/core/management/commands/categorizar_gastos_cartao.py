"""Comando Customizado do Django para Caracterização de Gastos de Cartão.

Corrige a base histórica: faturas consolidadas e compras individuais de cartão
criadas antes da caracterização automática ficaram sem categoria e por isso
apareciam como "Sem categoria" no detalhamento de "Maiores Gastos" do Dashboard.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Conta
from core.services.fatura_service import CATEGORIA_CARTAO_NOME, obter_categoria_cartao


class Command(BaseCommand):
    """Classe executora do backfill de categoria em lançamentos de cartão de crédito."""

    help = (
        "Atribui a categoria "
        f'"{CATEGORIA_CARTAO_NOME}" às faturas e compras de cartão sem categoria.'
    )

    def add_arguments(self, parser):
        """Declara as opções aceitas pelo comando.

        Args:
            parser (ArgumentParser): Parser de argumentos do comando.
        """
        parser.add_argument(
            "--usuario",
            dest="usuario",
            default=None,
            help="Restringe a correção ao username informado (padrão: todos).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas relata o que seria alterado, sem gravar nada.",
        )

    def handle(self, *args, **options):
        """Percorre os usuários preenchendo a categoria dos lançamentos de cartão.

        Args:
            *args: Argumentos posicionais.
            **options: Opções do terminal (`usuario`, `dry_run`).
        """
        dry_run = options["dry_run"]
        usuarios = get_user_model().objects.all()

        if options["usuario"]:
            usuarios = usuarios.filter(username=options["usuario"])
            if not usuarios.exists():
                self.stdout.write(
                    self.style.ERROR(f'Usuário "{options["usuario"]}" não encontrado.')
                )
                return

        total_faturas = 0
        total_compras = 0

        for usuario in usuarios:
            pendentes = Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                cartao__isnull=False,
                categoria__isnull=True,
            )

            faturas = pendentes.filter(eh_fatura_cartao=True).count()
            compras = pendentes.filter(eh_fatura_cartao=False).count()

            if not faturas and not compras:
                continue

            self.stdout.write(
                f"{usuario.username}: {faturas} fatura(s) e {compras} compra(s) sem categoria."
            )

            if not dry_run:
                with transaction.atomic():
                    categoria = obter_categoria_cartao(usuario)
                    # update() em massa não dispara os signals de consolidação —
                    # desejável aqui, já que os valores das faturas não mudam.
                    pendentes.update(categoria=categoria)

            total_faturas += faturas
            total_compras += compras

        if not total_faturas and not total_compras:
            self.stdout.write(
                self.style.SUCCESS("Nenhum lançamento de cartão sem categoria encontrado.")
            )
            return

        prefixo = "[dry-run] Seriam corrigidos" if dry_run else "Corrigidos"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefixo} {total_faturas} fatura(s) e {total_compras} compra(s) "
                f'de cartão com a categoria "{CATEGORIA_CARTAO_NOME}".'
            )
        )
