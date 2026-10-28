"""Testes do endpoint de sinais, do sinal no balanceamento e do tipo fiscal do ativo.

Cenário: na XP, 300 PETR4 a preço médio R$ 80 e 700 VALE3 a R$ 100, ambas cotadas a
R$ 100 — carteira de R$ 100 mil a mercado. Metas de 20% e 80%: PETR4 está em 30%, fora
da banda, e o sinal manda vender 100 cotas com R$ 2 mil de lucro.
Ver docs/proposta-sinais-realizacao.md.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from investimento.models import Ativo, Carteira, Cotacao, PosicaoCarteira, Transacao
from investimento.sinais import TipoFiscal

URL_SINAIS = "/api/investimentos/sinais/"
URL_BALANCEAMENTO = "/api/investimentos/balanceamento/"


class SinaisBaseTestCase(APITestCase):
    """Base com a carteira do cenário e a cotação do dia."""

    def setUp(self):
        """Cria o investidor, a XP com PETR4 e VALE3, e a Inter vazia."""
        self.user = self._autenticar("investidor-sinais")
        self.xp = Carteira.objects.get(usuario=self.user)
        self.inter = Carteira.objects.create(usuario=self.user, nome="Inter")

        self.petr4 = self._ativo("PETR4", cotacao="100")
        self.vale3 = self._ativo("VALE3", cotacao="100")
        self._ordem(self.petr4, self.xp, Transacao.TIPO_COMPRA, 300, "80")
        self._ordem(self.vale3, self.xp, Transacao.TIPO_COMPRA, 700, "100")
        self._meta(self.petr4, self.xp, "20")
        self._meta(self.vale3, self.xp, "80")

    def _autenticar(self, username):
        user = User.objects.create_user(username=username, password="senha-bem-comprida-123")
        token = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return user

    def _ativo(self, ticker, cotacao, usuario=None, **campos):
        ativo = Ativo.objects.create(usuario=usuario or self.user, ticker=ticker, **campos)
        Cotacao.objects.create(ativo=ativo, data=timezone.localdate(), valor=Decimal(cotacao))
        return ativo

    def _ordem(self, ativo, carteira, tipo, quantidade, preco, data=None):
        quantidade, preco = Decimal(quantidade), Decimal(preco)
        return Transacao.objects.create(
            usuario=ativo.usuario,
            ativo=ativo,
            carteira=carteira,
            tipo=tipo,
            data=data or timezone.localdate(),
            quantidade=quantidade,
            preco_unitario=preco,
            valor_total=quantidade * preco,
        )

    def _meta(self, ativo, carteira, meta):
        PosicaoCarteira.objects.filter(ativo=ativo, carteira=carteira).update(
            meta_porcentagem=Decimal(meta)
        )

    def _vender_no_mes(self, ticker, valor, data=None, **campos):
        # Compra e venda numa carteira sem metas, para não mexer no cenário da XP
        ativo = self._ativo(ticker, cotacao="100", **campos)
        cotas = Decimal(valor) / 100
        self._ordem(ativo, self.inter, Transacao.TIPO_COMPRA, cotas, "100", data=data)
        self._ordem(ativo, self.inter, Transacao.TIPO_VENDA, cotas, "100", data=data)


class EndpointSinaisTests(SinaisBaseTestCase):
    def test_lista_so_as_posicoes_com_sinal(self):
        resposta = self.client.get(URL_SINAIS)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["total"], 1)
        sinal = resposta.data["sinais"][0]
        self.assertEqual(sinal["ticker"], "PETR4")
        self.assertEqual(sinal["carteira_id"], self.xp.id)
        self.assertEqual(sinal["tipo"], "VENDER_COM_LUCRO")
        self.assertEqual(sinal["cotas_a_vender"], 100)
        self.assertEqual(sinal["resultado_venda"], 2000)
        self.assertEqual(sinal["isencao"], "ISENTA")

    def test_vendas_de_acoes_no_mes_entram_na_conta_da_isencao(self):
        self._vender_no_mes("ITUB4", "15000")

        resposta = self.client.get(URL_SINAIS)

        self.assertEqual(resposta.data["vendas_acoes_no_mes"], 15000)
        sinal = resposta.data["sinais"][0]
        self.assertEqual(sinal["isencao"], "EXCEDE")
        self.assertEqual(sinal["cotas_dentro_isencao"], 50)

    def test_venda_do_mes_anterior_nao_conta(self):
        mes_passado = timezone.localdate().replace(day=1) - datetime.timedelta(days=1)
        self._vender_no_mes("ITUB4", "15000", data=mes_passado)

        resposta = self.client.get(URL_SINAIS)

        self.assertEqual(resposta.data["vendas_acoes_no_mes"], 0)
        self.assertEqual(resposta.data["sinais"][0]["isencao"], "ISENTA")

    def test_venda_de_fii_nao_conta_para_a_isencao_de_acoes(self):
        self._vender_no_mes("HGLG11", "15000", tipo_fiscal=TipoFiscal.FII)

        resposta = self.client.get(URL_SINAIS)

        self.assertEqual(resposta.data["vendas_acoes_no_mes"], 0)

    def test_filtro_por_carteira(self):
        resposta = self.client.get(URL_SINAIS, {"carteira": self.inter.id})

        self.assertEqual(resposta.data["total"], 0)

    def test_sinais_de_outro_usuario_nao_aparecem(self):
        outro = User.objects.create_user(username="outro", password="senha-bem-comprida-123")
        alheio = self._ativo("BBAS3", cotacao="100", usuario=outro)
        carteira_alheia = Carteira.objects.get(usuario=outro)
        self._ordem(alheio, carteira_alheia, Transacao.TIPO_COMPRA, 10, "50")
        self._meta(alheio, carteira_alheia, "1")

        resposta = self.client.get(URL_SINAIS)

        self.assertEqual([s["ticker"] for s in resposta.data["sinais"]], ["PETR4"])

    def test_exige_autenticacao(self):
        self.client.credentials()

        self.assertEqual(self.client.get(URL_SINAIS).status_code, 401)


class BalanceamentoComSinalTests(SinaisBaseTestCase):
    def _ativo_no_plano(self, ticker):
        resposta = self.client.get(URL_BALANCEAMENTO, {"carteira": self.xp.id})
        ativos = [a for classe in resposta.data["classes"] for a in classe["ativos"]]
        return next(a for a in ativos if a["ticker"] == ticker)

    def test_traz_o_peso_a_mercado_ao_lado_do_peso_por_custo(self):
        petr4 = self._ativo_no_plano("PETR4")

        self.assertAlmostEqual(petr4["perc_mercado"], 30)
        self.assertAlmostEqual(petr4["valor_mercado"], 30000)
        # O peso por custo continua o mesmo: 24 mil de 94 mil investidos
        self.assertAlmostEqual(petr4["perc_atual"], 24000 / 94000 * 100)

    def test_traz_o_sinal_de_cada_ativo(self):
        self.assertEqual(self._ativo_no_plano("PETR4")["sinal"]["tipo"], "VENDER_COM_LUCRO")
        self.assertEqual(self._ativo_no_plano("VALE3")["sinal"]["tipo"], "SEM_SINAL")


class TipoFiscalDoAtivoTests(SinaisBaseTestCase):
    def test_tipo_fiscal_e_inferido_ao_cadastrar(self):
        self.assertEqual(self.petr4.tipo_fiscal, TipoFiscal.ACAO)

    def test_tipo_fiscal_informado_nao_e_sobrescrito(self):
        ativo = Ativo.objects.create(usuario=self.user, ticker="BOVA11", tipo_fiscal=TipoFiscal.ETF)

        self.assertEqual(ativo.tipo_fiscal, TipoFiscal.ETF)

    def test_api_permite_corrigir_o_tipo_fiscal(self):
        resposta = self.client.patch(
            f"/api/investimentos/ativos/{self.petr4.id}/", {"tipo_fiscal": "FII"}, format="json"
        )

        self.assertEqual(resposta.status_code, 200)
        self.petr4.refresh_from_db()
        self.assertEqual(self.petr4.tipo_fiscal, TipoFiscal.FII)
