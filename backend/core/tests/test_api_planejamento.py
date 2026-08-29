"""Testes dos endpoints de planejamento: horizonte de saldos e calendário.

Além do contrato das respostas, dois pontos merecem verificação explícita:

**Isolamento.** As duas telas somam e listam dinheiro. Um vazamento aqui não
mostraria o registro de outra pessoa numa tabela — apareceria embutido num total,
onde ninguém notaria. Por isso o teste compara saldos entre dois usuários com
dados diferentes, no padrão de `test_security.py`.

**Entrada malformada.** Ano e mês chegam pela query string. Um valor absurdo tem
de virar 400, nunca 500: `date(ano, mes, 1)` estoura para fora da faixa válida.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Conta, ConfigUsuario

User = get_user_model()


class PlanejamentoBaseTestCase(APITestCase):
    """Base com dois usuários, para que todo teste possa checar isolamento."""

    def setUp(self):
        """Cria a vítima e o curioso, cada um com o seu próprio caixa."""
        self.maria = User.objects.create_user(
            username="maria", password="senha-bem-comprida-123",
            email="maria@exemplo.com",
        )
        self.joao = User.objects.create_user(
            username="joao", password="senha-bem-comprida-123",
            email="joao@exemplo.com",
        )
        for usuario in (self.maria, self.joao):
            ConfigUsuario.objects.get_or_create(usuario=usuario)

        self.hoje = timezone.localdate()

        # Maria tem caixa e uma conta a vencer; João não tem nada.
        Conta.objects.create(
            usuario=self.maria, tipo=Conta.TIPO_RECEITA,
            descricao="Salário da Maria", valor=Decimal("9000.00"),
            data_prevista=self.hoje - timedelta(days=5),
            transacao_realizada=True, data_realizacao=self.hoje - timedelta(days=5),
        )
        Conta.objects.create(
            usuario=self.maria, tipo=Conta.TIPO_DESPESA,
            descricao="Aluguel da Maria", valor=Decimal("2500.00"),
            data_prevista=self.hoje + timedelta(days=3),
        )


class HorizonteSaldosAPITests(PlanejamentoBaseTestCase):
    """Cobre o endpoint de projeção de saldo."""

    def setUp(self):
        """Resolve a URL do horizonte."""
        super().setUp()
        self.url = reverse("api-planejamento-horizonte")

    def test_exige_autenticacao(self):
        """Projeção é dado financeiro: nunca anônima."""
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_devolve_a_janela_de_doze_meses_por_padrao(self):
        """O padrão da tela é um ano à frente."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data["meses"]), 12)

    def test_respeita_o_parametro_de_janela(self):
        """Permite encurtar a projeção sem recalcular no cliente."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url, {"meses": 3})
        self.assertEqual(len(resposta.data["meses"]), 3)

    def test_janela_absurda_e_limitada_em_vez_de_estourar(self):
        """Um parâmetro fora de faixa não deve virar consulta gigante nem erro."""
        self.client.force_authenticate(user=self.maria)

        resposta = self.client.get(self.url, {"meses": 9999})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(resposta.data["meses"]), 24)

        resposta = self.client.get(self.url, {"meses": "muitos"})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_limite_de_atencao_invalido_responde_400(self):
        """Entrada malformada é recusa clara, não erro do servidor."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url, {"limite_atencao": "muito"})

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limite_atencao", resposta.data)

    def test_saldo_de_um_usuario_nao_vaza_para_o_outro(self):
        """O vazamento aqui apareceria dentro de um total, onde ninguém notaria."""
        self.client.force_authenticate(user=self.joao)
        resposta = self.client.get(self.url, {"meses": 1})

        self.assertEqual(Decimal(resposta.data["saldo_inicial"]), Decimal("0.00"))
        # E nenhum dia da janela do João pode carregar o aluguel da Maria.
        totais = [
            Decimal(m["total_despesas"]) for m in resposta.data["meses"]
        ]
        self.assertEqual(sum(totais), Decimal("0.00"))

    def test_projecao_da_maria_reflete_os_dados_dela(self):
        """Contraprova do teste anterior: os dados certos aparecem para quem é dono."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url, {"meses": 1})

        self.assertEqual(Decimal(resposta.data["saldo_inicial"]), Decimal("9000.00"))
        self.assertEqual(
            Decimal(resposta.data["meses"][0]["total_despesas"]), Decimal("2500.00")
        )


class CalendarioAPITests(PlanejamentoBaseTestCase):
    """Cobre o endpoint do calendário de pagamentos e recebimentos."""

    def setUp(self):
        """Resolve a URL do calendário."""
        super().setUp()
        self.url = reverse("api-planejamento-calendario")

    def test_exige_autenticacao(self):
        """Agenda financeira também é dado do usuário."""
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_usa_o_mes_corrente_por_padrao(self):
        """Abrir a tela sem parâmetro precisa mostrar o mês de hoje."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["ano"], self.hoje.year)
        self.assertEqual(resposta.data["mes"], self.hoje.month)

    def test_mes_invalido_responde_400(self):
        """`date(ano, 13, 1)` estouraria; a recusa tem de vir antes disso."""
        self.client.force_authenticate(user=self.maria)

        for mes in (0, 13, -1):
            with self.subTest(mes=mes):
                resposta = self.client.get(self.url, {"ano": 2026, "mes": mes})
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ano_fora_de_faixa_responde_400(self):
        """Mesma proteção para o ano."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url, {"ano": 99999, "mes": 1})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parametro_nao_numerico_responde_400(self):
        """Entrada textual não pode chegar ao `int()` sem tratamento."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.get(self.url, {"ano": "abc", "mes": "def"})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calendario_do_joao_nao_mostra_lancamento_da_maria(self):
        """Isolamento no padrão de `test_security.py`."""
        self.client.force_authenticate(user=self.joao)
        resposta = self.client.get(
            self.url, {"ano": self.hoje.year, "mes": self.hoje.month}
        )

        todos = [
            item
            for dia in resposta.data["dias"]
            for item in dia["lancamentos"]
        ]
        self.assertEqual(todos, [])


class LiquidacaoAPITests(PlanejamentoBaseTestCase):
    """Cobre a liquidação feita a partir do calendário."""

    def setUp(self):
        """Prepara um lançamento pendente da Maria."""
        super().setUp()
        self.conta = Conta.objects.get(usuario=self.maria, descricao="Aluguel da Maria")
        self.url_liquidar = reverse(
            "api-planejamento-liquidar", args=[self.conta.pk]
        )
        self.url_desfazer = reverse(
            "api-planejamento-desfazer", args=[self.conta.pk]
        )

    def test_liquidar_marca_o_lancamento_como_realizado(self):
        """O caminho felizes da ação principal da tela."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.post(self.url_liquidar)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.data["realizado"])

        self.conta.refresh_from_db()
        self.assertTrue(self.conta.transacao_realizada)
        self.assertIsNotNone(self.conta.data_realizacao)

    def test_liquidar_aceita_data_explicita(self):
        """Permite registrar um pagamento feito em outro dia."""
        self.client.force_authenticate(user=self.maria)
        ontem = (self.hoje - timedelta(days=1)).isoformat()

        resposta = self.client.post(
            self.url_liquidar, {"data": ontem}, format="json"
        )
        self.assertEqual(resposta.data["data_realizacao"], ontem)

    def test_data_malformada_responde_400(self):
        """Formato inválido é recusa clara, não 500."""
        self.client.force_authenticate(user=self.maria)
        resposta = self.client.post(
            self.url_liquidar, {"data": "31/12/2026"}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.conta.refresh_from_db()
        self.assertFalse(self.conta.transacao_realizada)

    def test_desfazer_devolve_ao_estado_pendente(self):
        """Erro de clique precisa ser reversível."""
        self.client.force_authenticate(user=self.maria)
        self.client.post(self.url_liquidar)

        resposta = self.client.post(self.url_desfazer)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertFalse(resposta.data["realizado"])

        self.conta.refresh_from_db()
        self.assertFalse(self.conta.transacao_realizada)

    def test_liquidar_funciona_para_receita(self):
        """A ação do Kanban cobre só despesas; esta precisa servir aos dois tipos."""
        receita = Conta.objects.create(
            usuario=self.maria, tipo=Conta.TIPO_RECEITA,
            descricao="Freelance", valor=Decimal("800.00"),
            data_prevista=self.hoje,
        )
        self.client.force_authenticate(user=self.maria)

        resposta = self.client.post(
            reverse("api-planejamento-liquidar", args=[receita.pk])
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        receita.refresh_from_db()
        self.assertTrue(receita.transacao_realizada)

    def test_nao_liquida_lancamento_de_outro_usuario(self):
        """Responde 404, e não 403: a resposta não confirma que o id existe."""
        self.client.force_authenticate(user=self.joao)
        resposta = self.client.post(self.url_liquidar)

        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)
        self.conta.refresh_from_db()
        self.assertFalse(self.conta.transacao_realizada)

    def test_liquidacao_exige_autenticacao(self):
        """Escrita sem sessão é recusada."""
        self.assertEqual(
            self.client.post(self.url_liquidar).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
