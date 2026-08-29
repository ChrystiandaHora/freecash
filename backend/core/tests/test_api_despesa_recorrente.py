"""Testes da criação de despesa recorrente pela API de Contas a Pagar.

A recorrência existia apenas para receitas. Generalizá-la no modelo não bastava:
sem um caminho pela API, a despesa fixa continuaria inalcançável para o usuário e
a projeção de saldo seguiria otimista — receita fixa materializada doze meses à
frente, despesa fixa só nos meses lançados à mão.

O contrato reproduz o já usado pelas receitas: o campo `recorrencia` carrega a
frequência, e a sua presença é o que distingue um lançamento avulso de uma regra.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Conta, ConfigUsuario, LancamentoRecorrente

User = get_user_model()


class DespesaRecorrenteAPITests(APITestCase):
    """Cobre o caminho de criação de despesa fixa."""

    def setUp(self):
        """Autentica um usuário e resolve a URL de contas a pagar."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api-financeiro-contas-pagar-list")

    def _payload(self, **extra):
        """Monta um corpo válido de despesa recorrente.

        Returns:
            dict: Corpo pronto para envio.
        """
        base = {
            "descricao": "Aluguel",
            "valor": "2000.00",
            "data_vencimento": "2026-04-10",
            "categoria": "Moradia",
            "recorrencia": "mensal",
        }
        base.update(extra)
        return base

    def test_cria_regra_de_despesa_e_materializa_ocorrencias(self):
        """O caminho principal: uma regra e um ano de ocorrências futuras."""
        resposta = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

        regra = LancamentoRecorrente.objects.get(usuario=self.user)
        self.assertEqual(regra.tipo, LancamentoRecorrente.TIPO_DESPESA)
        self.assertEqual(regra.frequencia, LancamentoRecorrente.FREQ_MENSAL)
        self.assertEqual(regra.valor, Decimal("2000.00"))

        ocorrencias = Conta.objects.filter(usuario=self.user, recorrencia=regra)
        self.assertGreater(ocorrencias.count(), 1)
        # E todas precisam ser despesa, não receita.
        self.assertTrue(all(o.tipo == Conta.TIPO_DESPESA for o in ocorrencias))

    def test_primeira_ocorrencia_cai_na_data_informada(self):
        """A data de vencimento informada é a da primeira ocorrência."""
        self.client.post(self.url, self._payload(), format="json")

        primeira = (
            Conta.objects.filter(usuario=self.user).order_by("data_prevista").first()
        )
        self.assertEqual(primeira.data_prevista, date(2026, 4, 10))

    def test_sem_recorrencia_continua_criando_lancamento_avulso(self):
        """A generalização não pode transformar toda despesa em regra fixa."""
        payload = self._payload()
        del payload["recorrencia"]

        resposta = self.client.post(self.url, payload, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LancamentoRecorrente.objects.count(), 0)
        self.assertEqual(Conta.objects.filter(usuario=self.user).count(), 1)

    def test_frequencia_invalida_responde_400(self):
        """Entrada malformada é recusa por campo, não erro do servidor."""
        resposta = self.client.post(
            self.url, self._payload(recorrencia="a-cada-lua-cheia"), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recorrencia", resposta.data)
        self.assertEqual(LancamentoRecorrente.objects.count(), 0)

    def test_data_malformada_responde_400(self):
        """Formato de data inválido não pode chegar ao `strptime` sem tratamento."""
        resposta = self.client.post(
            self.url, self._payload(data_vencimento="10/04/2026"), format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_data_fim_limita_a_geracao(self):
        """Uma despesa com prazo definido não deve gerar ocorrências além dele."""
        self.client.post(
            self.url,
            self._payload(data_fim="2026-07-10"),
            format="json",
        )

        ultima = (
            Conta.objects.filter(usuario=self.user).order_by("-data_prevista").first()
        )
        self.assertLessEqual(ultima.data_prevista, date(2026, 7, 10))

    def test_regra_de_outro_usuario_nao_e_afetada(self):
        """Isolamento: criar uma regra não pode tocar dados de terceiros."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=outro)

        self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(
            LancamentoRecorrente.objects.filter(usuario=outro).count(), 0
        )
        self.assertEqual(Conta.objects.filter(usuario=outro).count(), 0)
