"""Testes unitários e de integração para a funcionalidade de Eventos fora do orçamento."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Categoria, Conta, CartaoCredito, Evento, PlanoMetas
from core.services.dashboard_helper import (
    totals_for_range_competencia,
    totals_for_range_realizadas,
    saldo_liquidez_ate,
    gastos_eventos_fora_orcamento,
)
from core.services import metas_service


class EventosTestCase(APITestCase):
    """Testes completos da funcionalidade de Eventos."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="StrongPassword123!"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="StrongPassword123!"
        )
        self.client.force_authenticate(user=self.user)

        self.cat_viagem = Categoria.objects.create(
            usuario=self.user, nome="Viagem", tipo=Categoria.TIPO_DESPESA
        )
        self.cat_alimentacao = Categoria.objects.create(
            usuario=self.user, nome="Alimentação", tipo=Categoria.TIPO_DESPESA
        )

    def test_evento_crud_e_isolamento(self):
        """Valida criação, listagem e isolamento multi-tenant de Eventos."""
        # Criar evento
        res = self.client.post(
            "/api/eventos/",
            {
                "nome": "Viagem Europa 2026",
                "inicio": "2026-10-01",
                "fim": "2026-10-15",
                "orcamento": "15000.00",
                "fora_dos_relatorios": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        evento_id = res.data["id"]

        # Listar eventos
        res_list = self.client.get("/api/eventos/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)
        self.assertEqual(res_list.data[0]["nome"], "Viagem Europa 2026")

        # Outro usuário não vê o evento
        self.client.force_authenticate(user=self.other_user)
        res_other = self.client.get("/api/eventos/")
        self.assertEqual(len(res_other.data), 0)

        res_detail_other = self.client.get(f"/api/eventos/{evento_id}/")
        self.assertEqual(res_detail_other.status_code, status.HTTP_404_NOT_FOUND)

    def test_regras_validacao_conta_evento(self):
        """Valida que despesa com evento só pode ser do tipo D, sem cartão, e do mesmo usuário."""
        evento = Evento.objects.create(
            usuario=self.user,
            nome="Reforma Sala",
            orcamento=Decimal("5000.00"),
        )
        evento_outro = Evento.objects.create(
            usuario=self.other_user,
            nome="Evento Alheio",
        )

        # 1. Não pode vincular evento de outro usuário
        res = self.client.post(
            "/api/financeiro/contas-pagar/",
            {
                "descricao": "Tinta",
                "valor": "250.00",
                "data_vencimento": "2026-10-10",
                "categoria": "Reforma",
                "evento": evento_outro.id,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Despesa direta válida vinculada ao evento
        res_ok = self.client.post(
            "/api/financeiro/contas-pagar/",
            {
                "descricao": "Tinta Coral",
                "valor": "250.00",
                "data_vencimento": "2026-10-10",
                "categoria": "Reforma",
                "evento": evento.id,
            },
            format="json",
        )
        self.assertEqual(res_ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_ok.data["evento"], evento.id)
        self.assertEqual(res_ok.data["evento_nome"], "Reforma Sala")

        # 3. Compras de cartão não podem ser vinculadas a evento
        cartao = CartaoCredito.objects.create(
            usuario=self.user,
            nome="Nubank",
            limite=Decimal("5000.00"),
            dia_fechamento=1,
            dia_vencimento=10,
        )
        conta_cartao = Conta(
            usuario=self.user,
            descricao="Passagem aérea",
            valor=Decimal("1500.00"),
            tipo=Conta.TIPO_DESPESA,
            data_prevista=date(2026, 10, 10),
            cartao=cartao,
            evento=evento,
        )
        with self.assertRaises(Exception):
            conta_cartao.full_clean()

    def test_protect_ao_excluir_evento_com_lancamentos(self):
        """Garante que on_delete=models.PROTECT impede exclusão de evento com lançamentos."""
        evento = Evento.objects.create(
            usuario=self.user,
            nome="Viagem Chile",
            orcamento=Decimal("8000.00"),
        )
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Passeio Cordilheira",
            valor=Decimal("600.00"),
            data_prevista=date(2026, 10, 5),
            evento=evento,
        )

        with self.assertRaises(ProtectedError):
            evento.delete()

    def test_do_orcamento_queryset_e_totais(self):
        """Valida que Conta.objects.do_orcamento() exclui despesas de eventos fora_dos_relatorios."""
        evento_fora = Evento.objects.create(
            usuario=self.user,
            nome="Viagem Fora",
            fora_dos_relatorios=True,
        )
        evento_dentro = Evento.objects.create(
            usuario=self.user,
            nome="Natal no Orçamento",
            fora_dos_relatorios=False,
        )

        # Despesa normal do mês: R$ 1.000,00
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Mercado",
            valor=Decimal("1000.00"),
            data_prevista=date(2026, 10, 5),
            transacao_realizada=True,
            data_realizacao=date(2026, 10, 5),
        )
        # Despesa de evento fora do orçamento: R$ 11.000,00
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Hospedagem Europa",
            valor=Decimal("11000.00"),
            data_prevista=date(2026, 10, 10),
            transacao_realizada=True,
            data_realizacao=date(2026, 10, 10),
            evento=evento_fora,
        )
        # Despesa de evento dentro do orçamento: R$ 500,00
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Presente Natal",
            valor=Decimal("500.00"),
            data_prevista=date(2026, 10, 15),
            transacao_realizada=True,
            data_realizacao=date(2026, 10, 15),
            evento=evento_dentro,
        )
        # Receita normal: R$ 15.000,00
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_RECEITA,
            descricao="Salário",
            valor=Decimal("15000.00"),
            data_prevista=date(2026, 10, 1),
            transacao_realizada=True,
            data_realizacao=date(2026, 10, 1),
        )

        # 1. Conta.objects.do_orcamento() exclui os R$ 11.000
        do_orc = Conta.objects.filter(usuario=self.user).do_orcamento()
        self.assertEqual(do_orc.filter(tipo=Conta.TIPO_DESPESA).count(), 2)

        # 2. Totais de competência: despesas devem ser 1000 + 500 = 1500 (NÃO 12500)
        rec, desp = totals_for_range_competencia(
            self.user, date(2026, 10, 1), date(2026, 11, 1)
        )
        self.assertEqual(desp, 1500.00)
        self.assertEqual(rec, 15000.00)

        # 3. Totais realizadas: despesas devem ser 1500
        rec_r, desp_r = totals_for_range_realizadas(
            self.user, date(2026, 10, 1), date(2026, 11, 1)
        )
        self.assertEqual(desp_r, 1500.00)

        # 4. Saldo de liquidez acumulado: DEVE incluir todos os desembolsos reais!
        # Saldo = 15000 - 1000 - 11000 - 500 = 2500.00
        saldo_real = saldo_liquidez_ate(self.user, date(2026, 10, 31))
        self.assertEqual(saldo_real, 2500.00)

        # 5. Gastos fora do orçamento helper
        fora = gastos_eventos_fora_orcamento(
            self.user, date(2026, 10, 1), date(2026, 11, 1)
        )
        self.assertEqual(len(fora), 1)
        self.assertEqual(fora[0]["evento_nome"], "Viagem Fora")
        self.assertEqual(fora[0]["total"], 11000.00)

    def test_dashboard_api_payload_gastos_fora_orcamento(self):
        """Valida que o endpoint do Dashboard expõe gastos_fora_orcamento sem sujar total_despesas."""
        evento = Evento.objects.create(
            usuario=self.user,
            nome="Viagem Japão 2026",
            fora_dos_relatorios=True,
        )
        # Despesa normal
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Luz",
            valor=Decimal("200.00"),
            data_prevista=date(2026, 10, 5),
        )
        # Despesa de viagem
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Trem-bala Shinkansen",
            valor=Decimal("1200.00"),
            data_prevista=date(2026, 10, 12),
            evento=evento,
        )

        res = self.client.get("/api/dashboard/?ano=2026&mes=10")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # total_despesas deve ser apenas 200.0
        self.assertEqual(res.data["total_despesas"], 200.0)
        # gastos_fora_orcamento deve ter 1200.0
        self.assertEqual(res.data["gastos_fora_orcamento"]["total"], 1200.0)
        self.assertEqual(len(res.data["gastos_fora_orcamento"]["eventos"]), 1)
        self.assertEqual(
            res.data["gastos_fora_orcamento"]["eventos"][0]["evento_nome"],
            "Viagem Japão 2026",
        )

    def test_relatorio_dre_e_metas_excluem_evento(self):
        """Valida que a DRE anual e o cálculo de custo de vida das metas excluem despesas de evento."""
        evento = Evento.objects.create(
            usuario=self.user,
            nome="Reforma Cozinha",
            fora_dos_relatorios=True,
        )
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Aluguel",
            valor=Decimal("3000.00"),
            data_prevista=date(2026, 10, 1),
        )
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Marcenaria Reforma",
            valor=Decimal("8000.00"),
            data_prevista=date(2026, 10, 15),
            evento=evento,
        )

        # DRE
        res_dre = self.client.get("/api/relatorios/dre/?ano=2026")
        self.assertEqual(res_dre.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(res_dre.data["despesas"]["despesas_fixas"])), Decimal("3000.00"))

        # Metas: custo de vida sugerido
        PlanoMetas.objects.create(usuario=self.user, meses_referencia=1)
        _, custo_medio = metas_service.medias_mensais(self.user, meses=1)
        # O custo médio deve ser 3000.00, NÃO 11000.00
        self.assertEqual(custo_medio, 3000.00)

    def test_evento_resumo_action(self):
        """Valida a rota /api/eventos/{id}/resumo/ com detalhe por categoria."""
        evento = Evento.objects.create(
            usuario=self.user,
            nome="Viagem Nordeste",
            orcamento=Decimal("6000.00"),
        )
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Pousada Maragogi",
            valor=Decimal("2500.00"),
            data_prevista=date(2026, 10, 10),
            transacao_realizada=True,
            data_realizacao=date(2026, 10, 10),
            categoria=self.cat_viagem,
            evento=evento,
        )
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Restaurante Frutos do Mar",
            valor=Decimal("500.00"),
            data_prevista=date(2026, 10, 11),
            transacao_realizada=False,
            categoria=self.cat_alimentacao,
            evento=evento,
        )

        res = self.client.get(f"/api/eventos/{evento.id}/resumo/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_realizado"], 2500.00)
        self.assertEqual(res.data["total_previsto"], 3000.00)
        self.assertEqual(res.data["saldo_restante"], 3000.00)
        self.assertEqual(len(res.data["categorias"]), 2)
        self.assertEqual(len(res.data["lancamentos"]), 2)

    def test_backup_restore_com_eventos(self):
        """Valida que backup exporta Evento e restore preserva o vínculo em Conta.evento."""
        from core.services.export_service import export_user_data
        from core.services.import_service import decrypt_data_fcbk, restore_user_data_fcbk

        evento = Evento.objects.create(
            usuario=self.user,
            nome="Viagem Portugal",
            orcamento=Decimal("12000.00"),
            fora_dos_relatorios=True,
        )
        conta = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Passaporte e Visto",
            valor=Decimal("650.00"),
            data_prevista=date(2026, 10, 8),
            evento=evento,
        )

        pwd = "SafeBackupPassword123!"
        encrypted_b64 = export_user_data(self.user, pwd)
        decrypted = decrypt_data_fcbk(encrypted_b64, pwd)

        # Restaura os dados
        res = restore_user_data_fcbk(decrypted, self.user)
        self.assertEqual(res["tipo"], "fcbk")

        # Verifica se o evento foi recriado e o vínculo mantido
        evento_restaurado = Evento.objects.filter(usuario=self.user, nome="Viagem Portugal").first()
        self.assertIsNotNone(evento_restaurado)
        self.assertEqual(evento_restaurado.orcamento, Decimal("12000.00"))

        conta_restaurada = Conta.objects.filter(usuario=self.user, descricao="Passaporte e Visto").first()
        self.assertIsNotNone(conta_restaurada)
        self.assertEqual(conta_restaurada.evento_id, evento_restaurado.id)

