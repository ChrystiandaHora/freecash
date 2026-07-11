"""Testes do serviço de geração de ocorrências de Receita Recorrente.

Cobre os pontos críticos do design (ver core/services/recorrencia_service.py):
geração idempotente, clamp de dia 31 em mês curto, pausa sem apagar histórico,
extensão de horizonte sob demanda e edição não retroativa.
"""

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Categoria, Conta, ReceitaRecorrente
from core.services.recorrencia_service import (
    gerar_ocorrencias,
    criar_regra_e_gerar,
    estender_horizonte_se_necessario,
    pausar_regra,
    propagar_edicao,
)


class RecorrenciaServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser_recorrencia", password="senha123")
        self.categoria = Categoria.objects.create(
            usuario=self.user, nome="Salário", tipo=Categoria.TIPO_RECEITA
        )

    def _criar_regra(self, frequencia="mensal", data_inicio=date(2026, 1, 31), data_fim=None):
        return ReceitaRecorrente.objects.create(
            usuario=self.user,
            descricao="Salário",
            categoria=self.categoria,
            valor=Decimal("5000.00"),
            frequencia=frequencia,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

    def test_geracao_idempotente(self):
        regra = self._criar_regra()
        criadas_1 = gerar_ocorrencias(regra, date(2026, 4, 30))
        criadas_2 = gerar_ocorrencias(regra, date(2026, 4, 30))

        self.assertEqual(criadas_1, 4)  # jan, fev, mar, abr
        self.assertEqual(criadas_2, 0)
        self.assertEqual(Conta.objects.filter(receita_recorrente=regra).count(), 4)

    def test_dia_31_cai_em_fevereiro_curto(self):
        regra = self._criar_regra(data_inicio=date(2026, 1, 31))
        gerar_ocorrencias(regra, date(2026, 3, 31))

        datas = sorted(
            Conta.objects.filter(receita_recorrente=regra).values_list("data_prevista", flat=True)
        )
        self.assertEqual(datas[0], date(2026, 1, 31))
        self.assertEqual(datas[1], date(2026, 2, 28))  # 2026 não é bissexto
        self.assertEqual(datas[2], date(2026, 3, 28))  # clamp segue a partir do dia 28

    def test_pausar_nao_remove_ocorrencias_existentes(self):
        regra = self._criar_regra()
        gerar_ocorrencias(regra, date(2026, 3, 31))
        total_antes = Conta.objects.filter(receita_recorrente=regra).count()

        pausar_regra(regra)
        regra.refresh_from_db()

        self.assertFalse(regra.ativa)
        self.assertEqual(Conta.objects.filter(receita_recorrente=regra).count(), total_antes)

        # E não gera mais nada mesmo se chamado diretamente após a pausa não é o
        # que barra a geração (isso é papel de estender_horizonte_se_necessario);
        # o teste de fato relevante é o de estender_horizonte abaixo.

    def test_estender_horizonte_respeita_regra_pausada(self):
        regra = self._criar_regra()
        gerar_ocorrencias(regra, date(2026, 1, 31))
        pausar_regra(regra)

        estender_horizonte_se_necessario(self.user, 6, 2026)

        self.assertEqual(Conta.objects.filter(receita_recorrente=regra).count(), 1)

    def test_estender_horizonte_gera_mes_futuro(self):
        regra = self._criar_regra()
        gerar_ocorrencias(regra, date(2026, 1, 31))

        estender_horizonte_se_necessario(self.user, 6, 2026)

        self.assertTrue(
            Conta.objects.filter(receita_recorrente=regra, data_prevista__month=6, data_prevista__year=2026).exists()
        )

    def test_criar_regra_e_gerar_retorna_primeira_ocorrencia(self):
        regra, primeira = criar_regra_e_gerar(
            usuario=self.user,
            descricao="Aluguel recebido",
            categoria=self.categoria,
            valor=Decimal("1500.00"),
            frequencia=ReceitaRecorrente.FREQ_MENSAL,
            data_inicio=date(2026, 3, 10),
        )
        self.assertEqual(primeira.data_prevista, date(2026, 3, 10))
        self.assertEqual(primeira.receita_recorrente_id, regra.id)
        self.assertGreater(Conta.objects.filter(receita_recorrente=regra).count(), 1)

    def test_edicao_nao_afeta_ocorrencia_ja_realizada(self):
        hoje = date.today()
        regra = self._criar_regra(data_inicio=hoje)
        gerar_ocorrencias(regra, hoje + relativedelta(months=2))

        realizada = Conta.objects.get(receita_recorrente=regra, data_prevista=hoje)
        realizada.marcar_realizada(hoje)

        propagar_edicao(regra, valor=Decimal("6000.00"), descricao="Salário Novo", categoria=self.categoria)

        realizada.refresh_from_db()
        futura = (
            Conta.objects.filter(receita_recorrente=regra)
            .exclude(id=realizada.id)
            .order_by("data_prevista")
            .first()
        )

        self.assertEqual(realizada.valor, Decimal("5000.00"))
        self.assertEqual(futura.valor, Decimal("6000.00"))
        self.assertEqual(futura.descricao, "Salário Novo")

    def test_respeita_data_fim(self):
        regra = self._criar_regra(data_inicio=date(2026, 1, 1), data_fim=date(2026, 2, 15))
        gerar_ocorrencias(regra, date(2026, 6, 1))

        datas = list(
            Conta.objects.filter(receita_recorrente=regra).values_list("data_prevista", flat=True)
        )
        self.assertEqual(sorted(datas), [date(2026, 1, 1), date(2026, 2, 1)])
