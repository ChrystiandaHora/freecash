"""Testes do backup das linhas de extrato importado.

`LinhaExtrato` pertence ao usuário só através do `ExtratoImportado`, então não é achada
pela descoberta automática. Antes da exportação manual, a restauração apagava os
extratos, os recriava vazios e as linhas sumiam em cascata, sem erro.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Conta, ExtratoImportado, LinhaExtrato
from core.services.export_service import coletar_dados_usuario
from core.services.import_service import restaurar_dados_usuario
from core.tests.backup_utils import exportar_e_ler


class BackupLinhaExtratoTests(TestCase):
    """Ida e volta das linhas de extrato, com os vínculos preservados."""

    def setUp(self):
        self.user = User.objects.create_user(username="extratos", password="senha-forte-123")
        self.conta = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Mercado",
            valor=Decimal("230.40"),
            data_prevista=date(2026, 9, 10),
        )
        self.extrato = ExtratoImportado.objects.create(
            usuario=self.user, arquivo_nome="fatura-setembro.pdf", banco="nubank"
        )
        self.conciliada = LinhaExtrato.objects.create(
            extrato=self.extrato,
            data=date(2026, 9, 10),
            descricao="MERCADO CENTRAL",
            valor=Decimal("230.40"),
            tipo="D",
            status="importado",
            conta_vinculada=self.conta,
        )
        self.pendente = LinhaExtrato.objects.create(
            extrato=self.extrato,
            data=date(2026, 9, 12),
            descricao="PADARIA",
            valor=Decimal("18.90"),
            tipo="D",
        )

    def test_linhas_entram_no_backup_com_os_uuids_dos_vinculos(self):
        linhas = coletar_dados_usuario(self.user)["data"]["core"]["LinhaExtrato"]

        por_uuid = {linha["uuid"]: linha for linha in linhas}
        self.assertEqual(set(por_uuid), {str(self.conciliada.uuid), str(self.pendente.uuid)})
        self.assertEqual(por_uuid[str(self.conciliada.uuid)]["extrato_uuid"], str(self.extrato.uuid))
        self.assertEqual(
            por_uuid[str(self.conciliada.uuid)]["conta_vinculada_uuid"], str(self.conta.uuid)
        )
        self.assertIsNone(por_uuid[str(self.pendente.uuid)]["conta_vinculada_uuid"])

    def test_restauracao_devolve_as_linhas_religadas(self):
        dados = exportar_e_ler(self.user)

        restaurar_dados_usuario(dados, self.user)

        conciliada = LinhaExtrato.objects.get(uuid=self.conciliada.uuid)
        self.assertEqual(conciliada.extrato.uuid, self.extrato.uuid)
        self.assertEqual(conciliada.conta_vinculada.uuid, self.conta.uuid)
        self.assertEqual(conciliada.valor, Decimal("230.40"))
        self.assertEqual(conciliada.status, "importado")
        pendente = LinhaExtrato.objects.get(uuid=self.pendente.uuid)
        self.assertIsNone(pendente.conta_vinculada)
        self.assertEqual(pendente.status, "pendente")

    def test_backup_sem_linhas_de_extrato_restaura_normalmente(self):
        dados = exportar_e_ler(self.user)
        del dados["data"]["core"]["LinhaExtrato"]

        restaurar_dados_usuario(dados, self.user)

        self.assertEqual(ExtratoImportado.objects.filter(usuario=self.user).count(), 1)
        self.assertEqual(LinhaExtrato.objects.count(), 0)
