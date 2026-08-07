"""Testes de backup e restauração do módulo de Metas Financeiras.

Cobre o ciclo completo exportar → restaurar, garantindo que a base de cálculo,
as metas (padrão e personalizadas) e o histórico de aportes sobrevivam intactos.

`AporteMeta` merece atenção especial: por não ter FK direta para o usuário, ele
não é descoberto por `get_backupable_models` e depende do tratamento manual no
serviço de exportação — sem ele, o histórico seria silenciosamente perdido.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import AporteMeta, MetaFinanceira, PlanoMetas
from core.services.export_service import export_user_data, get_backupable_models
from core.services.import_service import decrypt_data_fcbk, restore_user_data_fcbk

SENHA = "senha-de-backup-123"


class BackupMetasTests(TestCase):
    """Ciclo de exportação e restauração das metas do usuário."""

    def setUp(self):
        self.user = User.objects.create_user(username="chrystian", password="senha-forte-123")

        self.plano = PlanoMetas.objects.create(
            usuario=self.user,
            renda_mensal=Decimal("8093.68"),
            custo_vida_mensal=Decimal("6266.57"),
            meses_referencia=6,
        )

        self.patrimonio = MetaFinanceira.objects.create(
            usuario=self.user,
            nome="Patrimônio para viver de renda",
            tipo=MetaFinanceira.TIPO_PATRIMONIO_RENDA,
            base_calculo=MetaFinanceira.BASE_RENDA,
            multiplicador=Decimal("150"),  # multiplicador personalizado
            valor_alvo=Decimal("1214052.00"),
            origem_acumulado=MetaFinanceira.ORIGEM_CARTEIRA,
            ordem=1,
        )

        self.celular = MetaFinanceira.objects.create(
            usuario=self.user,
            nome="Compra de celular",
            tipo=MetaFinanceira.TIPO_PERSONALIZADA,
            valor_alvo=Decimal("5000.00"),
            valor_acumulado=Decimal("2000.00"),
            prazo="2026-12-31",
            observacao="Modelo com 256 GB",
        )

        for valor, obs in (("1200.00", "sobra do mês"), ("800.00", "freela")):
            AporteMeta.objects.create(
                meta=self.celular, data="2026-08-01", valor=Decimal(valor), observacao=obs
            )

    def _round_trip(self):
        """Exporta e restaura o backup no mesmo usuário.

        Returns:
            dict: Estatísticas devolvidas por `restore_user_data_fcbk`.
        """
        conteudo = export_user_data(self.user, SENHA)
        dados = decrypt_data_fcbk(conteudo, SENHA)
        return restore_user_data_fcbk(dados, self.user)

    # ── Cobertura da exportação ──────────────────────────────────────────────

    def test_modelos_de_metas_entram_na_descoberta_automatica(self):
        nomes = [m.__name__ for m in get_backupable_models()]

        self.assertIn("PlanoMetas", nomes)
        self.assertIn("MetaFinanceira", nomes)
        # AporteMeta não tem campo `usuario`: fica de fora da descoberta e é
        # tratado manualmente pelo serviço de exportação.
        self.assertNotIn("AporteMeta", nomes)

    def test_plano_meta_e_aportes_estao_no_arquivo_exportado(self):
        dados = decrypt_data_fcbk(export_user_data(self.user, SENHA), SENHA)
        core = dados["data"]["core"]

        self.assertEqual(len(core["PlanoMetas"]), 1)
        self.assertEqual(len(core["MetaFinanceira"]), 2)
        self.assertEqual(len(core["AporteMeta"]), 2)
        # O aporte guarda o UUID da meta, não o id local do banco de origem.
        self.assertEqual(
            {a["meta_uuid"] for a in core["AporteMeta"]}, {str(self.celular.uuid)}
        )

    # ── Cobertura da restauração ─────────────────────────────────────────────

    def test_restaura_a_base_de_calculo(self):
        conteudo = export_user_data(self.user, SENHA)
        # Só depois de exportar é que o plano some, simulando a perda de dados.
        self.plano.delete()

        restore_user_data_fcbk(decrypt_data_fcbk(conteudo, SENHA), self.user)

        plano = PlanoMetas.objects.get(usuario=self.user)
        self.assertEqual(plano.renda_mensal, Decimal("8093.68"))
        self.assertEqual(plano.custo_vida_mensal, Decimal("6266.57"))
        self.assertEqual(plano.meses_referencia, 6)

    def test_restaura_multiplicador_personalizado_e_origem(self):
        self._round_trip()

        meta = MetaFinanceira.objects.get(
            usuario=self.user, tipo=MetaFinanceira.TIPO_PATRIMONIO_RENDA
        )
        self.assertEqual(meta.multiplicador, Decimal("150.0000"))
        self.assertEqual(meta.origem_acumulado, MetaFinanceira.ORIGEM_CARTEIRA)
        self.assertEqual(meta.valor_alvo, Decimal("1214052.00"))

    def test_restaura_meta_personalizada_com_progresso_e_prazo(self):
        self._round_trip()

        meta = MetaFinanceira.objects.get(usuario=self.user, nome="Compra de celular")
        self.assertEqual(meta.valor_alvo, Decimal("5000.00"))
        self.assertEqual(meta.valor_acumulado, Decimal("2000.00"))
        self.assertEqual(str(meta.prazo), "2026-12-31")
        self.assertEqual(meta.observacao, "Modelo com 256 GB")

    def test_restaura_o_historico_de_aportes_vinculado_a_meta_certa(self):
        self._round_trip()

        meta = MetaFinanceira.objects.get(usuario=self.user, nome="Compra de celular")
        aportes = AporteMeta.objects.filter(meta=meta)

        self.assertEqual(aportes.count(), 2)
        self.assertEqual(
            sorted(a.valor for a in aportes), [Decimal("800.00"), Decimal("1200.00")]
        )
        self.assertEqual(
            {a.observacao for a in aportes}, {"sobra do mês", "freela"}
        )

    def test_restaurar_nao_soma_os_aportes_de_novo_no_acumulado(self):
        """Regressão: o acumulado vem pronto do backup e não pode dobrar."""
        self._round_trip()

        meta = MetaFinanceira.objects.get(usuario=self.user, nome="Compra de celular")
        # 2.000,00 — e não 2.000 + 1.200 + 800.
        self.assertEqual(meta.valor_acumulado, Decimal("2000.00"))

    def test_restauracao_e_idempotente(self):
        self._round_trip()
        self._round_trip()

        self.assertEqual(MetaFinanceira.objects.filter(usuario=self.user).count(), 2)
        self.assertEqual(
            AporteMeta.objects.filter(meta__usuario=self.user).count(), 2
        )

    def test_restauracao_substitui_metas_que_nao_estao_no_backup(self):
        conteudo = export_user_data(self.user, SENHA)

        # Depois do backup o usuário cria mais uma meta com aportes.
        extra = MetaFinanceira.objects.create(
            usuario=self.user, nome="Viagem", valor_alvo=Decimal("9000.00")
        )
        AporteMeta.objects.create(meta=extra, data="2026-08-05", valor=Decimal("100.00"))

        restore_user_data_fcbk(decrypt_data_fcbk(conteudo, SENHA), self.user)

        # A restauração substitui o estado: a meta posterior e o aporte dela somem.
        self.assertFalse(
            MetaFinanceira.objects.filter(usuario=self.user, nome="Viagem").exists()
        )
        self.assertEqual(AporteMeta.objects.filter(meta__usuario=self.user).count(), 2)


class BackupMetasIsolamentoTests(TestCase):
    """Garante que o backup de um usuário não vaza nem sobrescreve o de outro."""

    def setUp(self):
        self.maria = User.objects.create_user(username="maria", password="senha-forte-123")
        self.joao = User.objects.create_user(username="joao", password="senha-forte-123")

        self.meta_maria = MetaFinanceira.objects.create(
            usuario=self.maria, nome="Reserva da Maria", valor_alvo=Decimal("30000.00")
        )
        AporteMeta.objects.create(
            meta=self.meta_maria, data="2026-08-01", valor=Decimal("500.00")
        )

        self.meta_joao = MetaFinanceira.objects.create(
            usuario=self.joao, nome="Reserva do João", valor_alvo=Decimal("10000.00")
        )
        AporteMeta.objects.create(
            meta=self.meta_joao, data="2026-08-01", valor=Decimal("250.00")
        )

    def test_exportacao_nao_inclui_metas_de_outro_usuario(self):
        dados = decrypt_data_fcbk(export_user_data(self.joao, SENHA), SENHA)
        core = dados["data"]["core"]

        nomes = {m["nome"] for m in core["MetaFinanceira"]}
        self.assertEqual(nomes, {"Reserva do João"})
        self.assertEqual(len(core["AporteMeta"]), 1)
        self.assertEqual(Decimal(str(core["AporteMeta"][0]["valor"])), Decimal("250.00"))

    def test_restauracao_de_um_usuario_nao_apaga_dados_do_outro(self):
        conteudo = export_user_data(self.joao, SENHA)
        restore_user_data_fcbk(decrypt_data_fcbk(conteudo, SENHA), self.joao)

        self.assertTrue(
            MetaFinanceira.objects.filter(usuario=self.maria, nome="Reserva da Maria").exists()
        )
        self.assertEqual(AporteMeta.objects.filter(meta__usuario=self.maria).count(), 1)
