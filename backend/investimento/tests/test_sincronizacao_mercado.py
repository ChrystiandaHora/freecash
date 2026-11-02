"""Cobre a sincronização do telão e a tabela de ativos que ele exibe.

O ponto central é não deixar o IP do servidor ser bloqueado pelo TradingView: fora do
pregão, dentro do intervalo, com o lock tomado ou durante um backoff, a fonte não pode
ser chamada. Ver `services/sincronizacao_mercado.py`.
"""

import datetime
from decimal import Decimal
from unittest import mock
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from investimento.calculators import atualizar_cotacoes
from investimento.models import Ativo, Carteira, Cotacao, Transacao
from investimento.services import sincronizacao_mercado as sync
from investimento.services.limite_fonte import BACKOFF_MAXIMO, BACKOFF_MINIMO
from investimento.services.tradingview_screener import (
    TradingViewLimitado,
    TradingViewQuote,
    fetch_quotes_brazil,
)

User = get_user_model()

CAMINHO_TV = "investimento.calculators.fetch_quotes_brazil"
CAMINHO_CVM = "investimento.calculators.fetch_cvm_quotes"
CAMINHO_URLOPEN = "investimento.services.tradingview_screener.urlopen"

URL_TELAO = "/api/investimentos/telao/"
URL_SINCRONIZAR = "/api/investimentos/telao/sincronizar/"

SP = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 14h em Brasília: pregão aberto
QUARTA_14H = datetime.datetime(2026, 11, 4, 14, 0, tzinfo=SP)

# Cache local por teste: o DatabaseCache de produção dependeria de createcachetable
CACHES_DE_TESTE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "t-default"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "t-throttle"},
    "mercado": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "t-mercado"},
}


def cotacao_tv(ticker: str, valor: str) -> dict:
    """Resposta do TradingView com uma cotação, no formato de `fetch_quotes_brazil`."""
    simbolo = f"BMFBOVESPA:{ticker}"
    return {simbolo: TradingViewQuote(symbol=simbolo, close=Decimal(valor), as_of=datetime.date(2026, 11, 4))}


def limpar_caches():
    for alias in CACHES_DE_TESTE:
        caches[alias].clear()


@override_settings(CACHES=CACHES_DE_TESTE)
class GuardasDaSincronizacaoTests(TestCase):
    def setUp(self):
        limpar_caches()
        self.user = User.objects.create_user(username="telao", password="senha-comprida-123")
        self.petr4 = Ativo.objects.create(usuario=self.user, ticker="PETR4")

    def test_fora_do_pregao_nao_consulta_a_fonte(self):
        sabado = datetime.datetime(2026, 11, 7, 14, 0, tzinfo=SP)

        with mock.patch(CAMINHO_TV) as tv:
            resultado = sync.sincronizar_mercado(self.user, agora=sabado)

        tv.assert_not_called()
        self.assertEqual(resultado.status, sync.FORA_DO_PREGAO)
        self.assertEqual(resultado.proxima_em, datetime.datetime(2026, 11, 9, 9, 55, tzinfo=SP))

    def test_noite_de_sexta_aponta_para_a_abertura_de_segunda(self):
        sexta_noite = datetime.datetime(2026, 11, 6, 19, 0, tzinfo=SP)
        self.assertEqual(
            sync.proxima_abertura(sexta_noite), datetime.datetime(2026, 11, 9, 9, 55, tzinfo=SP)
        )

    def test_madrugada_de_dia_util_aponta_para_a_abertura_do_mesmo_dia(self):
        madrugada = datetime.datetime(2026, 11, 4, 6, 0, tzinfo=SP)
        self.assertFalse(sync.pregao_aberto(madrugada))
        self.assertEqual(
            sync.proxima_abertura(madrugada), datetime.datetime(2026, 11, 4, 9, 55, tzinfo=SP)
        )

    def test_feriado_da_b3_nao_consulta_a_fonte_e_diz_o_motivo(self):
        finados = datetime.datetime(2026, 11, 2, 14, 44, tzinfo=SP)

        with mock.patch(CAMINHO_TV) as tv:
            resultado = sync.sincronizar_mercado(self.user, agora=finados)

        tv.assert_not_called()
        self.assertEqual(resultado.status, sync.FORA_DO_PREGAO)
        self.assertEqual(resultado.motivo, "Finados")
        self.assertEqual(resultado.proxima_em, datetime.datetime(2026, 11, 3, 9, 55, tzinfo=SP))

    def test_depois_do_carnaval_reabre_na_quarta_de_cinzas_as_13h(self):
        sexta_antes = datetime.datetime(2026, 2, 13, 19, 0, tzinfo=SP)
        self.assertEqual(
            sync.proxima_abertura(sexta_antes), datetime.datetime(2026, 2, 18, 12, 55, tzinfo=SP)
        )

    def test_quarta_de_cinzas_de_manha_esta_fechado(self):
        manha = datetime.datetime(2026, 2, 18, 11, 0, tzinfo=SP)
        self.assertEqual(sync.motivo_pregao_fechado(manha), "Fora do horário de negociação")
        self.assertTrue(sync.pregao_aberto(manha.replace(hour=13)))

    def test_primeira_chamada_no_pregao_consulta_e_grava(self):
        with mock.patch(CAMINHO_TV, return_value=cotacao_tv("PETR4", "38.50")) as tv:
            resultado = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)

        tv.assert_called_once()
        self.assertEqual(resultado.status, sync.ATUALIZADO)
        self.assertEqual(resultado.count, 1)
        self.assertEqual(resultado.proxima_em, QUARTA_14H + sync.INTERVALO_SINCRONIZACAO)
        self.assertEqual(Cotacao.objects.get(ativo=self.petr4).valor, Decimal("38.50"))
        self.assertIsNotNone(resultado.atualizado_em)

    def test_nova_chamada_dentro_do_intervalo_nao_consulta(self):
        with mock.patch(CAMINHO_TV, return_value=cotacao_tv("PETR4", "38.50")) as tv:
            sync.sincronizar_mercado(self.user, agora=QUARTA_14H)
            resultado = sync.sincronizar_mercado(
                self.user, agora=QUARTA_14H + datetime.timedelta(minutes=5)
            )

        tv.assert_called_once()
        self.assertEqual(resultado.status, sync.EM_CACHE)
        self.assertEqual(resultado.proxima_em, QUARTA_14H + sync.INTERVALO_SINCRONIZACAO)

    def test_passado_o_intervalo_consulta_de_novo(self):
        with mock.patch(CAMINHO_TV, return_value=cotacao_tv("PETR4", "38.50")) as tv:
            sync.sincronizar_mercado(self.user, agora=QUARTA_14H)
            resultado = sync.sincronizar_mercado(
                self.user, agora=QUARTA_14H + datetime.timedelta(minutes=16)
            )

        self.assertEqual(tv.call_count, 2)
        self.assertEqual(resultado.status, sync.ATUALIZADO)

    def test_limite_da_fonte_faz_o_servidor_inteiro_recuar(self):
        outro = User.objects.create_user(username="outro", password="senha-comprida-123")
        Ativo.objects.create(usuario=outro, ticker="VALE3")

        with mock.patch(CAMINHO_TV, side_effect=TradingViewLimitado("429")) as tv:
            primeiro = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)
            segundo = sync.sincronizar_mercado(outro, agora=QUARTA_14H + datetime.timedelta(minutes=1))

        tv.assert_called_once()
        self.assertEqual(primeiro.status, sync.LIMITADO)
        self.assertEqual(primeiro.proxima_em, QUARTA_14H + BACKOFF_MINIMO)
        self.assertEqual(segundo.status, sync.LIMITADO)

    def test_retry_after_maior_que_o_minimo_prevalece(self):
        with mock.patch(CAMINHO_TV, side_effect=TradingViewLimitado("429", retry_after=3600)):
            resultado = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)

        self.assertEqual(resultado.proxima_em, QUARTA_14H + datetime.timedelta(hours=1))

    def test_retry_after_absurdo_e_limitado_ao_teto(self):
        with mock.patch(CAMINHO_TV, side_effect=TradingViewLimitado("429", retry_after=10**9)):
            resultado = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)

        self.assertEqual(resultado.proxima_em, QUARTA_14H + BACKOFF_MAXIMO)

    def test_falha_generica_da_fonte_nao_prende_o_ciclo(self):
        with mock.patch(CAMINHO_TV, side_effect=RuntimeError("HTTP 500")) as tv:
            primeiro = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)
            segundo = sync.sincronizar_mercado(
                self.user, agora=QUARTA_14H + sync.RETENTATIVA_APOS_FALHA
            )

        self.assertEqual(primeiro.status, sync.FALHOU)
        self.assertEqual(primeiro.proxima_em, QUARTA_14H + sync.RETENTATIVA_APOS_FALHA)
        self.assertEqual(tv.call_count, 2)
        self.assertEqual(segundo.status, sync.FALHOU)

    def test_lock_tomado_por_outra_tela_nao_consulta(self):
        caches["mercado"].add(f"lock:{self.user.pk}", True)

        with mock.patch(CAMINHO_TV) as tv:
            resultado = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)

        tv.assert_not_called()
        self.assertEqual(resultado.status, sync.EM_CACHE)

    def test_lock_e_liberado_depois_da_consulta(self):
        with mock.patch(CAMINHO_TV, return_value={}):
            sync.sincronizar_mercado(self.user, agora=QUARTA_14H)

        self.assertIsNone(caches["mercado"].get(f"lock:{self.user.pk}"))

    def test_cvm_roda_no_maximo_uma_vez_por_dia(self):
        Ativo.objects.create(usuario=self.user, ticker="FUNDO", cnpj="12345678000199")
        cota = (Decimal("1.234"), datetime.date(2026, 11, 3))

        with (
            mock.patch(CAMINHO_TV, return_value=cotacao_tv("PETR4", "38.50")),
            mock.patch(CAMINHO_CVM, return_value={"12345678000199": cota}) as cvm,
        ):
            sync.sincronizar_mercado(self.user, agora=QUARTA_14H)
            sync.sincronizar_mercado(self.user, agora=QUARTA_14H + datetime.timedelta(minutes=16))
            self.assertEqual(cvm.call_count, 1)

            sync.sincronizar_mercado(self.user, agora=QUARTA_14H + datetime.timedelta(days=1))
            self.assertEqual(cvm.call_count, 2)

    def test_erros_nao_trazem_ticker_de_outro_usuario(self):
        outro = User.objects.create_user(username="vizinho", password="senha-comprida-123")
        Ativo.objects.create(usuario=outro, ticker="SEGR3")

        with mock.patch(CAMINHO_TV, return_value={}):
            resultado = sync.sincronizar_mercado(self.user, agora=QUARTA_14H)

        self.assertTrue(any("PETR4" in erro for erro in resultado.errors))
        self.assertFalse(any("SEGR3" in erro for erro in resultado.errors))


@override_settings(CACHES=CACHES_DE_TESTE)
class BotaoManualComLimiteTests(TestCase):
    def setUp(self):
        limpar_caches()
        self.user = User.objects.create_user(username="manual", password="senha-comprida-123")
        Ativo.objects.create(usuario=self.user, ticker="PETR4")
        self.sem_yahoo = mock.patch("investimento.calculators.fetch_historico_yahoo", return_value=[])
        self.sem_yahoo.start()
        self.addCleanup(self.sem_yahoo.stop)

    def test_limite_vira_erro_sem_interromper_o_botao_manual(self):
        with mock.patch(CAMINHO_TV, side_effect=TradingViewLimitado("HTTP 429")):
            count, erros, _ = atualizar_cotacoes(usuario=self.user)

        self.assertEqual(count, 0)
        self.assertTrue(any("HTTP 429" in erro for erro in erros))

    def test_limite_no_botao_manual_pausa_o_telao(self):
        with mock.patch(CAMINHO_TV, side_effect=TradingViewLimitado("HTTP 429")):
            atualizar_cotacoes(usuario=self.user)

        # O botão gravou a pausa com o relógio real; o pregão é fixado para o teste não depender do dia
        with (
            mock.patch(CAMINHO_TV) as tv,
            mock.patch("investimento.services.sincronizacao_mercado.motivo_pregao_fechado", return_value=None),
        ):
            resultado = sync.sincronizar_mercado(self.user)

        tv.assert_not_called()
        self.assertEqual(resultado.status, sync.LIMITADO)

    def test_botao_manual_respeita_a_pausa_da_fonte(self):
        with mock.patch(CAMINHO_TV, side_effect=TradingViewLimitado("HTTP 429")):
            atualizar_cotacoes(usuario=self.user)

        with mock.patch(CAMINHO_TV) as tv:
            _, erros, _ = atualizar_cotacoes(usuario=self.user)

        tv.assert_not_called()
        self.assertTrue(any("pausa" in erro for erro in erros))

    def test_falha_generica_nao_acusa_cada_ativo_de_nao_encontrado(self):
        with mock.patch(CAMINHO_TV, side_effect=RuntimeError("timeout")):
            _, erros, _ = atualizar_cotacoes(usuario=self.user)

        self.assertFalse(any("Não encontrado" in erro for erro in erros))


class LimiteDoTradingViewTests(TestCase):
    def _http_error(self, codigo, headers=None):
        return HTTPError("https://scanner.tradingview.com", codigo, "erro", headers or {}, None)

    def test_429_vira_limite_com_retry_after(self):
        with mock.patch(CAMINHO_URLOPEN, side_effect=self._http_error(429, {"Retry-After": "120"})):
            with self.assertRaises(TradingViewLimitado) as ctx:
                fetch_quotes_brazil(["PETR4"])

        self.assertEqual(ctx.exception.retry_after, 120)

    def test_retry_after_em_formato_de_data_e_ignorado(self):
        cabecalho = {"Retry-After": "Wed, 04 Nov 2026 15:00:00 GMT"}
        with mock.patch(CAMINHO_URLOPEN, side_effect=self._http_error(429, cabecalho)):
            with self.assertRaises(TradingViewLimitado) as ctx:
                fetch_quotes_brazil(["PETR4"])

        self.assertIsNone(ctx.exception.retry_after)

    def test_erro_500_continua_falha_generica(self):
        with mock.patch(CAMINHO_URLOPEN, side_effect=self._http_error(500)):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_quotes_brazil(["PETR4"])

        self.assertNotIsInstance(ctx.exception, TradingViewLimitado)


@override_settings(CACHES=CACHES_DE_TESTE)
class TelaoAPITests(APITestCase):
    def setUp(self):
        limpar_caches()
        self.user = self._autenticar("investidor-telao")
        self.carteira = Carteira.objects.get(usuario=self.user)
        hoje = timezone.localdate()
        self.ontem = hoje - datetime.timedelta(days=1)

        self.petr4 = self._ativo_com_posicao("PETR4", quantidade=10, preco="20", ontem="20", hoje="22")
        self.vale3 = self._ativo_com_posicao("VALE3", quantidade=5, preco="60", ontem="60", hoje="57")

    def _autenticar(self, username):
        user = User.objects.create_user(username=username, password="senha-bem-comprida-123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return user

    def _ativo_com_posicao(self, ticker, *, quantidade, preco, ontem, hoje, usuario=None, carteira=None):
        usuario = usuario or self.user
        ativo = Ativo.objects.create(usuario=usuario, ticker=ticker)
        quantidade, preco = Decimal(quantidade), Decimal(preco)
        Transacao.objects.create(
            usuario=usuario,
            ativo=ativo,
            carteira=carteira or Carteira.objects.get(usuario=usuario),
            tipo=Transacao.TIPO_COMPRA,
            data=self.ontem,
            quantidade=quantidade,
            preco_unitario=preco,
            valor_total=quantidade * preco,
        )
        Cotacao.objects.create(ativo=ativo, data=self.ontem, valor=Decimal(ontem))
        Cotacao.objects.create(ativo=ativo, data=timezone.localdate(), valor=Decimal(hoje))
        return ativo

    def test_exige_autenticacao(self):
        self.client.credentials()
        self.assertEqual(self.client.get(URL_TELAO).status_code, 401)
        self.assertEqual(self.client.post(URL_SINCRONIZAR).status_code, 401)

    def test_linhas_trazem_variacao_do_dia_valor_e_peso(self):
        resposta = self.client.get(URL_TELAO)

        self.assertEqual(resposta.status_code, 200)
        linhas = {linha["ticker"]: linha for linha in resposta.data["ativos"]}
        self.assertAlmostEqual(linhas["PETR4"]["variacao_dia_pct"], 10.0)
        self.assertAlmostEqual(linhas["VALE3"]["variacao_dia_pct"], -5.0)
        self.assertAlmostEqual(linhas["VALE3"]["valor"], 285.0)
        self.assertAlmostEqual(linhas["PETR4"]["peso_pct"] + linhas["VALE3"]["peso_pct"], 100.0)
        self.assertIsNotNone(resposta.data["cotacoes_atualizadas_em"])

    def test_ordena_da_maior_posicao_para_a_menor(self):
        resposta = self.client.get(URL_TELAO)
        self.assertEqual([linha["ticker"] for linha in resposta.data["ativos"]], ["VALE3", "PETR4"])

    def test_sem_pregao_anterior_a_variacao_fica_nula(self):
        ativo = Ativo.objects.create(usuario=self.user, ticker="ITSA4")
        Transacao.objects.create(
            usuario=self.user, ativo=ativo, carteira=self.carteira, tipo=Transacao.TIPO_COMPRA,
            data=self.ontem, quantidade=Decimal(1), preco_unitario=Decimal(10), valor_total=Decimal(10),
        )
        Cotacao.objects.create(ativo=ativo, data=timezone.localdate(), valor=Decimal("11"))

        resposta = self.client.get(URL_TELAO)

        linha = next(linha for linha in resposta.data["ativos"] if linha["ticker"] == "ITSA4")
        self.assertIsNone(linha["variacao_dia_pct"])

    def test_nao_expoe_ativos_de_outro_usuario(self):
        outro = User.objects.create_user(username="alheio", password="senha-bem-comprida-123")
        self._ativo_com_posicao("SEGR3", quantidade=1, preco="10", ontem="10", hoje="10", usuario=outro)

        resposta = self.client.get(URL_TELAO)

        self.assertNotIn("SEGR3", [linha["ticker"] for linha in resposta.data["ativos"]])

    def test_filtro_por_carteira_alheia_devolve_vazio(self):
        outro = User.objects.create_user(username="dono", password="senha-bem-comprida-123")
        carteira_alheia = Carteira.objects.get(usuario=outro)

        resposta = self.client.get(URL_TELAO, {"carteira": carteira_alheia.pk})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["ativos"], [])

    def test_sincronizar_fora_do_pregao_responde_200_com_status(self):
        with (
            mock.patch("investimento.services.sincronizacao_mercado.motivo_pregao_fechado", return_value="Finados"),
            mock.patch(CAMINHO_TV) as tv,
        ):
            resposta = self.client.post(URL_SINCRONIZAR)

        tv.assert_not_called()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["status"], sync.FORA_DO_PREGAO)
        self.assertEqual(resposta.data["motivo"], "Finados")
        self.assertIn("proxima_em", resposta.data)
