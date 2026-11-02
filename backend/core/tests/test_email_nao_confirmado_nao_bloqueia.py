"""Testes de que o e-mail não confirmado não bloqueia nenhuma ação da conta.

A confirmação do e-mail serve à recuperação de senha, e só. Ela já foi exigida para
importar, depois de uma carência de dias, e isso impedia o dono de trazer os próprios
dados para o sistema — o aviso na tela de Minha Conta e no sino de notificações passou
a ser a única consequência de não confirmar.

Contas legadas, sem endereço nenhum, entram no mesmo caso: não há o que confirmar, e
nada deve ser recusado por isso.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ConfigUsuario

User = get_user_model()

IDADE_CONTA_ANTIGA_DIAS = 30


class EmailNaoConfirmadoNaoBloqueiaTests(APITestCase):
    """Cobre importação, exportação e CRUD de uma conta antiga sem e-mail confirmado."""

    def setUp(self):
        """Cria uma conta antiga com e-mail cadastrado e não confirmado."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.user.date_joined = timezone.now() - timedelta(days=IDADE_CONTA_ANTIGA_DIAS)
        self.user.save(update_fields=["date_joined"])
        self.url_exportar = reverse("api-ferramentas-exportar")
        self.url_importar = reverse("api-ferramentas-importar")

    def _autenticar(self):
        """Autentica com uma instância recém-carregada do usuário."""
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))

    def _remover_email(self):
        """Simula a conta legada, criada antes de o e-mail virar obrigatório."""
        self.user.email = ""
        self.user.save(update_fields=["email"])

    # ── Importar ─────────────────────────────────────────────────────────────

    def test_importar_funciona_sem_email_confirmado(self):
        """O caso que motivou a mudança: conta antiga recebia 403 ao importar."""
        self._autenticar()
        resposta = self.client.post(self.url_importar, {}, format="multipart")
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_importar_funciona_para_conta_legada_sem_email(self):
        """Sem endereço também não há recusa."""
        self._remover_email()
        self._autenticar()
        resposta = self.client.post(self.url_importar, {}, format="multipart")
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_importar_extrato_e_conciliacao_funcionam_sem_email_confirmado(self):
        """As duas rotas de PDF tinham o mesmo portão que a restauração."""
        self._autenticar()
        for nome in ("api-ferramentas-importar-extrato", "api-ferramentas-conciliacao-upload"):
            with self.subTest(rota=nome):
                resposta = self.client.post(reverse(nome), {}, format="multipart")
                self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    # ── Exportar ─────────────────────────────────────────────────────────────

    def test_exportar_funciona_sem_email_confirmado(self):
        """Exportar os próprios dados nunca dependeu do e-mail."""
        self._autenticar()
        resposta = self.client.get(self.url_exportar, {"formato": "csv"})
        self.assertNotEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_backup_funciona_para_conta_legada_sem_email(self):
        """Conta sem endereço consegue gerar o backup."""
        self._remover_email()
        self._autenticar()

        resposta = self.client.post(
            reverse("api-ferramentas-backup"), {"senha": "senha-do-backup-forte"}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    # ── CRUD financeiro ──────────────────────────────────────────────────────

    def test_crud_financeiro_funciona_sem_email_confirmado(self):
        """O dono dos dados sempre registra seus próprios lançamentos."""
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
        self.assertIn(criacao.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_anonimo_continua_recebendo_401(self):
        """Tirar o portão de e-mail não pode abrir a rota para quem não está logado."""
        self.assertEqual(
            self.client.post(self.url_importar, {}, format="multipart").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(self.url_exportar, {"formato": "csv"}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
