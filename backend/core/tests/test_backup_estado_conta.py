"""Testes da fronteira entre preferências e estado da conta na restauração do backup.

`ConfigUsuario` entra no backup inteiro, mas parte dele descreve a conta, não os dados
financeiros: a confirmação do e-mail. Restaurar um arquivo gerado antes da confirmação
não pode desfazê-la — senão a importação seguinte cai no portão de e-mail não
verificado (ver docs/backup.md).
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import ConfigUsuario
from core.services.import_service import restaurar_dados_usuario
from core.tests.backup_utils import exportar_e_ler


class RestauracaoPreservaEstadoDaContaTests(TestCase):
    """A restauração aplica as preferências do backup e preserva a verificação atual."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="estado_conta", email="estado@exemplo.com", password="senha_123"
        )
        self.config, _ = ConfigUsuario.objects.get_or_create(usuario=self.user)

    def _backup_atual(self) -> dict:
        """Exporta e lê de volta o backup do usuário no estado presente.

        Returns:
            dict: O conteúdo do `dados.json`, pronto para `restaurar_dados_usuario`.
        """
        return exportar_e_ler(self.user)

    def _confirmar_email(self):
        self.config.email_verificado = True
        self.config.email_verificado_em = timezone.now()
        self.config.email_pendente = ""
        self.config.save()

    def test_backup_anterior_a_confirmacao_nao_desfaz_a_verificacao(self):
        backup = self._backup_atual()
        self._confirmar_email()
        confirmado_em = self.config.email_verificado_em

        restaurar_dados_usuario(backup, self.user)

        self.config.refresh_from_db()
        self.assertTrue(self.config.email_verificado)
        self.assertEqual(self.config.email_verificado_em, confirmado_em)

    def test_backup_nao_reabre_troca_de_email_ja_resolvida(self):
        self.config.email_pendente = "antigo@exemplo.com"
        self.config.save()
        backup = self._backup_atual()
        self._confirmar_email()

        restaurar_dados_usuario(backup, self.user)

        self.config.refresh_from_db()
        self.assertEqual(self.config.email_pendente, "")

    def test_backup_de_conta_confirmada_nao_confirma_conta_atual(self):
        self._confirmar_email()
        backup = self._backup_atual()
        self.config.email_verificado = False
        self.config.email_verificado_em = None
        self.config.save()

        restaurar_dados_usuario(backup, self.user)

        self.config.refresh_from_db()
        self.assertFalse(self.config.email_verificado)
        self.assertIsNone(self.config.email_verificado_em)

    def test_preferencias_do_backup_continuam_restauradas(self):
        self.config.moeda_padrao = "USD"
        self.config.save()
        backup = self._backup_atual()
        self.config.moeda_padrao = "BRL"
        self.config.save()

        restaurar_dados_usuario(backup, self.user)

        self.config.refresh_from_db()
        self.assertEqual(self.config.moeda_padrao, "USD")
