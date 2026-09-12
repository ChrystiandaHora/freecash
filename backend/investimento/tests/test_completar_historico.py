"""Cobre o completamento automático de histórico da atualização em lote.

O coletor de cotação atual grava um pregão por rodada, então um ativo recém-cadastrado
levaria dois meses de cliques diários até ter gráfico. `completar_historico` fecha essa
lacuna buscando a série no Yahoo — mas só de quem precisa, e sem repetir a consulta de
quem o Yahoo não conhece.
"""

import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from investimento.calculators import (
    JANELA_HISTORICO_DIAS,
    LIMITE_HISTORICO_POR_RODADA,
    REVERIFICAR_APOS_DIAS,
    completar_historico,
)
from investimento.models import Ativo, Cotacao
from investimento.services.yahoo_service import YahooIndisponivel

User = get_user_model()

CAMINHO_YAHOO = "investimento.calculators.fetch_historico_yahoo"


def serie_de(dias: int, *, ate=None) -> list[tuple[datetime.date, Decimal]]:
    """Monta uma série sintética de `dias` pregões terminando em `ate` (padrão: hoje)."""
    fim = ate or timezone.localdate()
    return [
        (fim - datetime.timedelta(days=i), Decimal("10.00") + Decimal(i))
        for i in reversed(range(dias))
    ]


class CompletarHistoricoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hist", password="senha-comprida-123")
        self.hoje = timezone.localdate()
        self.base = Ativo.objects.filter(usuario=self.user, ativo=True)

    def _ativo(self, ticker="PETR4", **kwargs):
        return Ativo.objects.create(usuario=self.user, ticker=ticker, **kwargs)

    def test_ativo_sem_cotacao_nenhuma_recebe_a_serie(self):
        ativo = self._ativo()
        erros = []

        with mock.patch(CAMINHO_YAHOO, return_value=serie_de(40)) as buscar:
            gravados, pendentes = completar_historico(self.base, erros)

        buscar.assert_called_once_with(ativo.ticker)
        self.assertEqual(gravados, 40)
        self.assertEqual(pendentes, 0)
        self.assertEqual(erros, [])
        self.assertEqual(Cotacao.objects.filter(ativo=ativo).count(), 40)

    def test_ativo_que_ja_cobre_a_janela_nao_gera_requisicao(self):
        ativo = self._ativo()
        Cotacao.objects.create(
            ativo=ativo,
            data=self.hoje - datetime.timedelta(days=JANELA_HISTORICO_DIAS),
            valor=Decimal("30.00"),
        )
        erros = []

        with mock.patch(CAMINHO_YAHOO) as buscar:
            gravados, pendentes = completar_historico(self.base, erros)

        buscar.assert_not_called()
        self.assertEqual((gravados, pendentes, erros), (0, 0, []))

    def test_ativo_com_historico_curto_e_completado(self):
        ativo = self._ativo()
        # Só as duas últimas semanas: o começo da janela está descoberto
        for i in range(14):
            Cotacao.objects.create(
                ativo=ativo, data=self.hoje - datetime.timedelta(days=i), valor=Decimal("30.00")
            )
        erros = []

        with mock.patch(CAMINHO_YAHOO, return_value=serie_de(45)) as buscar:
            gravados, _ = completar_historico(self.base, erros)

        buscar.assert_called_once()
        self.assertEqual(gravados, 45)

    def test_serie_sobrescreve_a_cotacao_ja_gravada_na_mesma_data(self):
        ativo = self._ativo()
        Cotacao.objects.create(ativo=ativo, data=self.hoje, valor=Decimal("99.00"))

        with mock.patch(CAMINHO_YAHOO, return_value=[(self.hoje, Decimal("31.50"))]):
            completar_historico(self.base, [])

        self.assertEqual(Cotacao.objects.get(ativo=ativo, data=self.hoje).valor, Decimal("31.50"))

    def test_ativo_sem_ticker_fica_de_fora(self):
        self._ativo(ticker="")

        with mock.patch(CAMINHO_YAHOO) as buscar:
            completar_historico(self.base, [])

        buscar.assert_not_called()

    def test_falha_no_yahoo_vira_erro_e_nao_derruba_o_lote(self):
        self._ativo(ticker="LFTS11")
        self._ativo(ticker="PETR4")
        erros = []

        with mock.patch(
            CAMINHO_YAHOO,
            side_effect=[YahooIndisponivel("Ticker não encontrado."), serie_de(30)],
        ):
            gravados, _ = completar_historico(self.base, erros)

        # O segundo ativo foi buscado mesmo com o primeiro falhando
        self.assertEqual(gravados, 30)
        self.assertEqual(len(erros), 1)
        self.assertIn("LFTS11", erros[0])

    def test_ticker_que_falhou_nao_e_reconsultado_na_rodada_seguinte(self):
        self._ativo(ticker="LFTS11")

        with mock.patch(CAMINHO_YAHOO, side_effect=YahooIndisponivel("desconhecido")):
            completar_historico(self.base, [])

        # Carimbar na falha é o que impede o mesmo erro a cada clique
        with mock.patch(CAMINHO_YAHOO) as buscar:
            _, pendentes = completar_historico(self.base, [])

        buscar.assert_not_called()
        self.assertEqual(pendentes, 0)

    def test_ativo_verificado_ha_muito_tempo_volta_a_ser_conferido(self):
        self._ativo(
            historico_verificado_em=self.hoje
            - datetime.timedelta(days=REVERIFICAR_APOS_DIAS + 1)
        )

        with mock.patch(CAMINHO_YAHOO, return_value=serie_de(20)) as buscar:
            completar_historico(self.base, [])

        buscar.assert_called_once()

    def test_teto_por_rodada_deixa_o_resto_pendente(self):
        excedente = 3
        for i in range(LIMITE_HISTORICO_POR_RODADA + excedente):
            self._ativo(ticker=f"TICK{i}")

        with mock.patch(CAMINHO_YAHOO, return_value=serie_de(5)) as buscar:
            _, pendentes = completar_historico(self.base, [])

        self.assertEqual(buscar.call_count, LIMITE_HISTORICO_POR_RODADA)
        self.assertEqual(pendentes, excedente)

    def test_ativo_de_outro_usuario_nao_entra(self):
        outro = User.objects.create_user(username="outro", password="senha-comprida-123")
        Ativo.objects.create(usuario=outro, ticker="VALE3")

        with mock.patch(CAMINHO_YAHOO) as buscar:
            completar_historico(self.base, [])

        buscar.assert_not_called()

    def test_conferencia_de_cobertura_nao_faz_uma_consulta_por_ativo(self):
        for i in range(8):
            ativo = self._ativo(ticker=f"COB{i}")
            Cotacao.objects.create(
                ativo=ativo,
                data=self.hoje - datetime.timedelta(days=JANELA_HISTORICO_DIAS),
                valor=Decimal("10.00"),
            )

        # Duas consultas: a lista de candidatos e a agregação de cobertura. O número é
        # fixo, e não proporcional aos oito ativos — é o que faz a checagem ser "rápida".
        with mock.patch(CAMINHO_YAHOO):
            with self.assertNumQueries(2):
                completar_historico(self.base, [])
