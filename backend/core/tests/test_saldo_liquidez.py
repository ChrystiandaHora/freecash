"""
Testes da liquidez realizada — o dinheiro em caixa hoje.

Esse número ancora a projeção diária do simulador: é dele que a curva parte. Se
ele vier errado, o dia em que o saldo cruza o zero e a margem necessária para
atravessar o horizonte saem errados junto. Daí a cobertura do regime de caixa
(só o que foi realizado, só até hoje) e do caso do cartão, onde a compra
individual não pode somar junto da fatura consolidada.
"""

from decimal import Decimal

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from core.models import CartaoCredito, Conta
from core.services.dashboard_helper import saldo_liquidez_ate

User = get_user_model()


class SaldoLiquidezServiceTests(APITestCase):
    """Verifica o cálculo de `saldo_liquidez_ate`."""

    def setUp(self):
        self.user = User.objects.create_user(username="chrystian", password="senha-forte-123")
        self.hoje = timezone.localdate()

    def _conta(self, tipo, valor, *, realizada=True, data_realizacao=None, **extra):
        """Cria uma Conta do usuário de teste com competência e caixa no mesmo dia.

        Args:
            tipo (str): `Conta.TIPO_RECEITA` ou `Conta.TIPO_DESPESA`.
            valor (str): Valor do lançamento.
            realizada (bool): Se o lançamento já foi efetivado.
            data_realizacao (date): Data de caixa. Assume hoje quando realizada.

        Returns:
            Conta: O lançamento persistido.
        """
        if realizada and data_realizacao is None:
            data_realizacao = self.hoje
        return Conta.objects.create(
            usuario=self.user,
            tipo=tipo,
            descricao=f"{tipo}-{valor}",
            valor=Decimal(valor),
            data_prevista=data_realizacao or self.hoje,
            transacao_realizada=realizada,
            data_realizacao=data_realizacao if realizada else None,
            **extra,
        )

    def test_saldo_e_a_diferenca_entre_receitas_e_despesas_realizadas(self):
        self._conta(Conta.TIPO_RECEITA, "6000.00")
        self._conta(Conta.TIPO_DESPESA, "2000.00")

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 4000.00)

    def test_saldo_pode_ser_negativo(self):
        self._conta(Conta.TIPO_RECEITA, "1000.00")
        self._conta(Conta.TIPO_DESPESA, "2500.00")

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), -1500.00)

    def test_sem_lancamentos_o_saldo_e_zero(self):
        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 0.0)

    def test_lancamento_nao_realizado_e_ignorado(self):
        self._conta(Conta.TIPO_RECEITA, "6000.00")
        # Conta a receber ainda pendente: é projeção, não caixa.
        self._conta(Conta.TIPO_RECEITA, "9999.00", realizada=False)
        self._conta(Conta.TIPO_DESPESA, "500.00", realizada=False)

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 6000.00)

    def test_realizacao_futura_nao_entra_no_saldo_de_hoje(self):
        self._conta(Conta.TIPO_RECEITA, "1000.00")
        self._conta(
            Conta.TIPO_RECEITA,
            "7000.00",
            data_realizacao=self.hoje + timedelta(days=1),
        )

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 1000.00)
        # A mesma consulta um dia à frente já enxerga o lançamento.
        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje + timedelta(days=1)), 8000.00)

    def test_saldo_acumula_desde_o_inicio_do_historico(self):
        # A soma é aberta no início: não há janela recortando meses antigos.
        self._conta(Conta.TIPO_RECEITA, "3000.00", data_realizacao=self.hoje - timedelta(days=400))
        self._conta(Conta.TIPO_DESPESA, "500.00", data_realizacao=self.hoje - timedelta(days=200))
        self._conta(Conta.TIPO_RECEITA, "1000.00")

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 3500.00)

    def test_saldo_nao_carrega_ruido_de_ponto_flutuante(self):
        # Centavos que, somados em float, produziriam algo como 52162.32999999999.
        self._conta(Conta.TIPO_RECEITA, "52362.43")
        self._conta(Conta.TIPO_DESPESA, "200.10")

        saldo = saldo_liquidez_ate(self.user, self.hoje)

        self.assertEqual(saldo, 52162.33)
        self.assertEqual(repr(saldo), "52162.33")

    def test_nao_conta_em_dobro_compra_de_cartao_e_fatura(self):
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Nubank", ultimos_digitos="1234"
        )
        self._conta(Conta.TIPO_RECEITA, "5000.00")

        # A compra individual dispara o signal que consolida a fatura do período.
        self._conta(Conta.TIPO_DESPESA, "400.00", cartao=cartao, eh_fatura_cartao=False)

        fatura = Conta.objects.filter(
            usuario=self.user, cartao=cartao, eh_fatura_cartao=True
        ).first()
        self.assertIsNotNone(fatura, "A fatura consolidada deveria ter sido criada pelo signal.")

        # Só a fatura conta como saída de caixa — a compra individual já está nela.
        fatura.transacao_realizada = True
        fatura.data_realizacao = self.hoje
        fatura.save()

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 4600.00)

    def test_saldo_e_isolado_por_usuario(self):
        outro = User.objects.create_user(username="outra-pessoa", password="senha-forte-123")
        self._conta(Conta.TIPO_RECEITA, "6000.00")
        Conta.objects.create(
            usuario=outro,
            tipo=Conta.TIPO_RECEITA,
            descricao="Salário alheio",
            valor=Decimal("50000.00"),
            data_prevista=self.hoje,
            transacao_realizada=True,
            data_realizacao=self.hoje,
        )

        self.assertEqual(saldo_liquidez_ate(self.user, self.hoje), 6000.00)
        self.assertEqual(saldo_liquidez_ate(outro, self.hoje), 50000.00)


class SaldoAtualAPITests(APITestCase):
    """Verifica o endpoint `GET /api/saldo-atual/` consumido pelo simulador."""

    def setUp(self):
        self.user = User.objects.create_user(username="chrystian", password="senha-forte-123")
        self.hoje = timezone.localdate()

    def _autenticar(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}")

    def test_exige_autenticacao(self):
        response = self.client.get("/api/saldo-atual/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retorna_saldo_e_data_de_referencia(self):
        self._autenticar()
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_RECEITA,
            descricao="Salário",
            valor=Decimal("4200.50"),
            data_prevista=self.hoje,
            transacao_realizada=True,
            data_realizacao=self.hoje,
        )

        response = self.client.get("/api/saldo-atual/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["saldo"], 4200.50)
        self.assertEqual(response.data["data_referencia"], self.hoje.isoformat())

    def test_parametro_ate_ancora_a_projecao_na_vespera(self):
        # O simulador ancora na véspera da janela para não contar duas vezes o que
        # já foi realizado entre o primeiro dia projetado e hoje.
        self._autenticar()
        ontem = self.hoje - timedelta(days=1)
        for data, valor in ((ontem, "1000.00"), (self.hoje, "300.00")):
            Conta.objects.create(
                usuario=self.user,
                tipo=Conta.TIPO_RECEITA,
                descricao=f"Entrada {data}",
                valor=Decimal(valor),
                data_prevista=data,
                transacao_realizada=True,
                data_realizacao=data,
            )

        response = self.client.get("/api/saldo-atual/", {"ate": ontem.isoformat()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["saldo"], 1000.00)
        self.assertEqual(response.data["data_referencia"], ontem.isoformat())

    def test_data_invalida_no_parametro_ate_cai_em_hoje(self):
        self._autenticar()

        response = self.client.get("/api/saldo-atual/", {"ate": "nao-e-data"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data_referencia"], self.hoje.isoformat())
