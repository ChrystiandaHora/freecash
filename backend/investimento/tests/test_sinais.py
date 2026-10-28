"""Testes da regra de sinais de realização e rebalanceamento.

A regra é função pura, então os testes não tocam o banco. O cenário base é uma
carteira de R$ 100 mil com 300 cotas a R$ 100 (30% a mercado) e meta de 20%: banda de
5 p.p., sobrepeso de 10 p.p., venda de 100 cotas para voltar à meta.
Ver docs/proposta-sinais-realizacao.md.
"""

from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase

from investimento.sinais import (
    PosicaoAvaliada,
    SituacaoIsencao,
    TipoFiscal,
    TipoSinal,
    avaliar_posicao,
)

TOTAL_CARTEIRA = Decimal("100000")

BASE = PosicaoAvaliada(
    quantidade=Decimal("300"),
    preco_medio=Decimal("80"),
    cotacao=Decimal("100"),
    meta_porcentagem=Decimal("20"),
    tipo_fiscal=TipoFiscal.ACAO,
)


def _avaliar(vendas_acoes_no_mes=Decimal("0"), **campos):
    return avaliar_posicao(
        replace(BASE, **campos),
        total_mercado_carteira=TOTAL_CARTEIRA,
        vendas_acoes_no_mes=vendas_acoes_no_mes,
    )


class BandaTests(SimpleTestCase):
    def test_posicao_dentro_da_banda_nao_gera_sinal(self):
        sinal = _avaliar(meta_porcentagem=Decimal("28"))

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)
        self.assertEqual(sinal.cotas_a_vender, 0)

    def test_sobrepeso_com_lucro_sugere_voltar_a_meta(self):
        sinal = _avaliar()

        self.assertEqual(sinal.tipo, TipoSinal.VENDER_COM_LUCRO)
        self.assertEqual(sinal.peso_mercado, Decimal("30"))
        self.assertEqual(sinal.banda, Decimal("5"))
        self.assertEqual(sinal.cotas_a_vender, Decimal("100"))
        self.assertEqual(sinal.valor_venda, Decimal("10000.00"))
        self.assertEqual(sinal.resultado_venda, Decimal("2000.00"))

    def test_banda_relativa_governa_metas_pequenas(self):
        # Meta de 4%: 25% dela é 1 p.p., menor que os 5 p.p. absolutos
        no_limite = _avaliar(meta_porcentagem=Decimal("4"), quantidade=Decimal("50"))
        acima = _avaliar(meta_porcentagem=Decimal("4"), quantidade=Decimal("51"))

        self.assertEqual(no_limite.tipo, TipoSinal.SEM_SINAL)
        self.assertEqual(acima.banda, Decimal("1"))
        self.assertEqual(acima.tipo, TipoSinal.VENDER_COM_LUCRO)
        self.assertEqual(acima.cotas_a_vender, Decimal("11"))

    def test_banda_absoluta_governa_metas_grandes(self):
        dentro = _avaliar(meta_porcentagem=Decimal("40"), quantidade=Decimal("440"))
        fora = _avaliar(meta_porcentagem=Decimal("40"), quantidade=Decimal("460"))

        self.assertEqual(dentro.tipo, TipoSinal.SEM_SINAL)
        self.assertEqual(fora.banda, Decimal("5"))
        self.assertEqual(fora.cotas_a_vender, Decimal("60"))

    def test_excesso_menor_que_uma_cota_nao_sinaliza(self):
        # 5,5% contra limite de 5%, mas o excesso de R$ 1.500 não paga uma cota de R$ 5.500
        sinal = _avaliar(
            meta_porcentagem=Decimal("4"),
            quantidade=Decimal("1"),
            cotacao=Decimal("5500"),
            preco_medio=Decimal("5000"),
        )

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)

    def test_meta_zero_nao_vira_ordem_de_zerar_posicao(self):
        sinal = _avaliar(meta_porcentagem=Decimal("0"))

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)


class ResultadoDaVendaTests(SimpleTestCase):
    def test_sobrepeso_com_prejuizo_sinaliza_venda_com_prejuizo(self):
        sinal = _avaliar(preco_medio=Decimal("120"))

        self.assertEqual(sinal.tipo, TipoSinal.VENDER_COM_PREJUIZO)
        self.assertEqual(sinal.resultado_venda, Decimal("-2000.00"))
        self.assertFalse(sinal.queda_relevante)

    def test_venda_no_preco_medio_conta_como_lucro(self):
        sinal = _avaliar(preco_medio=Decimal("100"))

        self.assertEqual(sinal.tipo, TipoSinal.VENDER_COM_LUCRO)
        self.assertEqual(sinal.resultado_venda, Decimal("0.00"))


class QuedaRelevanteTests(SimpleTestCase):
    def test_queda_de_20_por_cento_sem_sobrepeso_pede_revisao(self):
        sinal = _avaliar(preco_medio=Decimal("125"), meta_porcentagem=Decimal("30"))

        self.assertEqual(sinal.tipo, TipoSinal.REVISAR_QUEDA)
        self.assertTrue(sinal.queda_relevante)
        self.assertEqual(sinal.variacao_preco_medio, Decimal("-20"))
        self.assertEqual(sinal.cotas_a_vender, 0)

    def test_queda_menor_que_20_por_cento_nao_sinaliza(self):
        sinal = _avaliar(preco_medio=Decimal("124.99"), meta_porcentagem=Decimal("30"))

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)
        self.assertFalse(sinal.queda_relevante)

    def test_sobrepeso_com_queda_relevante_continua_sendo_venda(self):
        sinal = _avaliar(preco_medio=Decimal("150"))

        self.assertEqual(sinal.tipo, TipoSinal.VENDER_COM_PREJUIZO)
        self.assertTrue(sinal.queda_relevante)

    def test_queda_relevante_vale_mesmo_sem_meta(self):
        sinal = _avaliar(preco_medio=Decimal("150"), meta_porcentagem=Decimal("0"))

        self.assertEqual(sinal.tipo, TipoSinal.REVISAR_QUEDA)


class ForaDoEscopoTests(SimpleTestCase):
    def test_renda_fixa_nunca_sinaliza(self):
        sinal = _avaliar(tipo_fiscal=TipoFiscal.RENDA_FIXA, preco_medio=Decimal("150"))

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)
        self.assertFalse(sinal.queda_relevante)

    def test_sem_cotacao_nao_sinaliza(self):
        sinal = _avaliar(cotacao=None)

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)

    def test_posicao_zerada_nao_sinaliza(self):
        sinal = _avaliar(quantidade=Decimal("0"), preco_medio=Decimal("150"))

        self.assertEqual(sinal.tipo, TipoSinal.SEM_SINAL)

    def test_preco_medio_zerado_nao_derruba_o_calculo(self):
        # Ativo recebido por bonificação, sem custo de aquisição
        sinal = _avaliar(preco_medio=Decimal("0"))

        self.assertEqual(sinal.tipo, TipoSinal.VENDER_COM_LUCRO)
        self.assertIsNone(sinal.variacao_preco_medio)
        self.assertEqual(sinal.resultado_venda, Decimal("10000.00"))


class IsencaoTests(SimpleTestCase):
    def test_sem_venda_a_isencao_nao_se_aplica(self):
        sinal = _avaliar(meta_porcentagem=Decimal("28"))

        self.assertEqual(sinal.isencao, SituacaoIsencao.NAO_SE_APLICA)

    def test_venda_de_acao_dentro_dos_20_mil_e_isenta(self):
        sinal = _avaliar()

        self.assertEqual(sinal.isencao, SituacaoIsencao.ISENTA)
        self.assertIsNone(sinal.cotas_dentro_isencao)

    def test_venda_que_fecha_exatamente_20_mil_ainda_e_isenta(self):
        sinal = _avaliar(vendas_acoes_no_mes=Decimal("10000"))

        self.assertEqual(sinal.isencao, SituacaoIsencao.ISENTA)

    def test_venda_que_estoura_os_20_mil_indica_cotas_que_cabem(self):
        sinal = _avaliar(vendas_acoes_no_mes=Decimal("15000"))

        self.assertEqual(sinal.isencao, SituacaoIsencao.EXCEDE)
        self.assertEqual(sinal.cotas_dentro_isencao, Decimal("50"))

    def test_mes_ja_acima_do_limite_nao_deixa_cota_isenta(self):
        sinal = _avaliar(vendas_acoes_no_mes=Decimal("25000"))

        self.assertEqual(sinal.isencao, SituacaoIsencao.EXCEDE)
        self.assertEqual(sinal.cotas_dentro_isencao, 0)

    def test_venda_com_prejuizo_tambem_pode_estourar_a_isencao(self):
        # O limite é sobre valor vendido: a venda no prejuízo torna tributáveis as lucrativas do mês
        sinal = _avaliar(preco_medio=Decimal("120"), vendas_acoes_no_mes=Decimal("15000"))

        self.assertEqual(sinal.isencao, SituacaoIsencao.EXCEDE)

    def test_fii_e_sempre_tributavel(self):
        sinal = _avaliar(tipo_fiscal=TipoFiscal.FII)

        self.assertEqual(sinal.isencao, SituacaoIsencao.TRIBUTAVEL)

    def test_etf_e_tratado_como_tributavel(self):
        sinal = _avaliar(tipo_fiscal=TipoFiscal.ETF)

        self.assertEqual(sinal.isencao, SituacaoIsencao.TRIBUTAVEL)
