"""Testes do portão de e-mail confirmado aplicado à importação.

A regra distingue por **amplificação**, não por importância: o CRUD financeiro
nunca é bloqueado (punir o dono não protege ninguém); exportar também não, porque
uma conta descartável não tem dados para exportar — e bloquear ali contradizia a
tela de exclusão, que orienta exportar antes de apagar; importar é bloqueado após a
carência, porque processa arquivo enviado com leitores de PDF e planilha.

Caso de borda que motivou correção: contas sem endereço nenhum. Dizer "confirme seu
e-mail" a elas é um beco sem saída — não há o que confirmar e o reenvio recusa a
operação. A mensagem passou a apontar para Minha Conta.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ConfigUsuario

User = get_user_model()


@override_settings(EMAIL_VERIFICATION_GRACE_DAYS=7)
class EmailVerificadoOuCarenciaTests(APITestCase):
    """Cobre o portão aplicado à importação, e a ausência dele na exportação."""

    def setUp(self):
        """Cria um usuário recém-cadastrado, com e-mail não confirmado."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.url_exportar = reverse("api-ferramentas-exportar")
        self.url_importar = reverse("api-ferramentas-importar")

    def _autenticar(self):
        """Autentica com uma instância recém-carregada do usuário."""
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))

    def _envelhecer_conta(self, dias: int):
        """Recua a data de cadastro para simular o fim da carência."""
        self.user.date_joined = timezone.now() - timedelta(days=dias)
        self.user.save(update_fields=["date_joined"])

    # ── Exportar: nunca bloqueado ────────────────────────────────────────────

    def test_exportar_funciona_dentro_da_carencia(self):
        """Conta nova exporta sem atrito."""
        self._autenticar()
        resposta = self.client.get(self.url_exportar, {"formato": "csv"})
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_exportar_funciona_depois_da_carencia_sem_email_confirmado(self):
        """Exportar os próprios dados não é ação amplificadora.

        Este teste substitui um anterior, que afirmava o oposto. O portão havia sido
        aplicado à exportação por engano: uma conta descartável não tem dados para
        exportar, e bloquear ali tirava do usuário o acesso ao próprio acervo —
        inclusive o backup que a tela de exclusão de conta manda fazer antes de
        apagar tudo.
        """
        self._envelhecer_conta(30)
        self._autenticar()

        resposta = self.client.get(self.url_exportar, {"formato": "csv"})
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_exportar_funciona_para_conta_legada_sem_email(self):
        """O caso concreto que apareceu em uso real.

        Conta criada antes de o e-mail virar obrigatório, com a carência vencida,
        recebia 403 ao tentar exportar um backup — e a mensagem pedia para confirmar
        um e-mail que não existia.
        """
        self.user.email = ""
        self.user.save(update_fields=["email"])
        self._envelhecer_conta(30)
        self._autenticar()

        resposta = self.client.get(self.url_exportar, {"formato": "fcbk"})
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    # ── Importar: bloqueado após a carência ──────────────────────────────────

    def test_importar_funciona_dentro_da_carencia(self):
        """Conta nova importa sem atrito."""
        self._autenticar()
        resposta = self.client.post(self.url_importar, {}, format="multipart")
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_importar_bloqueia_apos_a_carencia_sem_email_confirmado(self):
        """Passada a carência, importar exige e-mail confirmado."""
        self._envelhecer_conta(30)
        self._autenticar()

        resposta = self.client.post(self.url_importar, {}, format="multipart")
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_email_confirmado_libera_importar(self):
        """Confirmado o e-mail, a idade da conta deixa de importar."""
        self._envelhecer_conta(30)
        config = ConfigUsuario.objects.get(usuario=self.user)
        config.email_verificado = True
        config.save()
        self._autenticar()

        resposta = self.client.post(self.url_importar, {}, format="multipart")
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_conta_sem_email_recebe_mensagem_acionavel(self):
        """A recusa precisa dizer o que fazer, e não pedir o impossível.

        "Reenvie a confirmação" era inútil para quem não tem endereço: o endpoint de
        reenvio recusa a operação nesse caso.
        """
        self.user.email = ""
        self.user.save(update_fields=["email"])
        self._envelhecer_conta(30)
        self._autenticar()

        resposta = self.client.post(self.url_importar, {}, format="multipart")

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        mensagem = str(resposta.data.get("detail", ""))
        self.assertIn("Minha Conta", mensagem)
        self.assertNotIn("Reenvie", mensagem)

    def test_conta_com_email_recebe_a_mensagem_de_confirmacao(self):
        """Quem tem endereço deve ser orientado a confirmá-lo, não a cadastrar outro."""
        self._envelhecer_conta(30)
        self._autenticar()

        resposta = self.client.post(self.url_importar, {}, format="multipart")

        mensagem = str(resposta.data.get("detail", ""))
        self.assertIn("Reenvie", mensagem)

    # ── CRUD financeiro: nunca bloqueado ─────────────────────────────────────

    def test_crud_financeiro_nunca_e_bloqueado(self):
        """O dono dos dados sempre registra seus próprios lançamentos.

        Se este teste falhar, o portão foi aplicado onde não devia.
        """
        self._envelhecer_conta(30)
        self._autenticar()

        listagem = self.client.get(reverse("api-conta-list"))
        self.assertEqual(listagem.status_code, status.HTTP_200_OK)

        criacao = self.client.post(
            reverse("api-conta-list"),
            {
                "tipo": "D",
                "descricao": "Conta de luz",
                "valor": "150.00",
                "data_prevista": timezone.localdate().isoformat(),
            },
            format="json",
        )
        self.assertIn(
            criacao.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK],
            f"CRUD financeiro bloqueado indevidamente: {criacao.status_code}",
        )

    def test_anonimo_continua_recebendo_401(self):
        """A permissão não deve mascarar a falta de autenticação."""
        self.assertEqual(
            self.client.post(self.url_importar, {}, format="multipart").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(self.url_exportar, {"formato": "csv"}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
