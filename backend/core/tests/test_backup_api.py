"""Testes dos endpoints de backup completo e de relatórios.

A senha do backup viajava na query string de um GET (`?senha=...`), e com isso ficava
gravada em log de acesso, proxy e histórico do navegador. O backup passou a ser gerado
por POST, com a senha no corpo, e o GET de exportação ficou só com os relatórios.
O backup é um ZIP AES-256 (ver docs/backup.md).
"""

import io

import pyzipper
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ConfigUsuario

User = get_user_model()

SENHA_DO_BACKUP = "senha-do-backup-forte"

# Cache local: sem isolar o throttle, a contagem vazaria entre os testes.
CACHES_DE_TESTE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


@override_settings(CACHES=CACHES_DE_TESTE)
class BackupAPITests(APITestCase):
    """POST /api/ferramentas/backup/."""

    def setUp(self):
        caches["throttle"].clear()
        self.user = User.objects.create_user(username="ana", password="senha-bem-comprida-123")
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api-ferramentas-backup")

    def test_gera_o_backup_como_zip_anexo(self):
        resposta = self.client.post(self.url, {"senha": SENHA_DO_BACKUP}, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta["Content-Type"], "application/zip")
        self.assertIn('.zip"', resposta["Content-Disposition"])
        with pyzipper.AESZipFile(io.BytesIO(resposta.content)) as zf:
            zf.setpassword(SENHA_DO_BACKUP.encode())
            self.assertIn("dados.json", zf.namelist())

    def test_registra_a_data_do_ultimo_backup(self):
        self.client.post(self.url, {"senha": SENHA_DO_BACKUP}, format="json")

        self.assertIsNotNone(ConfigUsuario.objects.get(usuario=self.user).ultimo_export_em)

    def test_recusa_sem_senha(self):
        resposta = self.client.post(self.url, {}, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recusa_senha_curta(self):
        resposta = self.client.post(self.url, {"senha": "a" * 11}, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_informa_que_ainda_nao_houve_backup(self):
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), {"ultimo_backup_em": None})

    def test_get_informa_a_data_do_ultimo_backup(self):
        self.client.post(self.url, {"senha": SENHA_DO_BACKUP}, format="json")

        resposta = self.client.get(self.url)

        esperado = ConfigUsuario.objects.get(usuario=self.user).ultimo_export_em
        self.assertEqual(resposta.json()["ultimo_backup_em"], esperado.isoformat())

    def test_get_nao_gasta_o_limite_de_geracao(self):
        for _ in range(15):
            self.client.get(self.url)

        resposta = self.client.post(self.url, {"senha": SENHA_DO_BACKUP}, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_get_ignora_senha_na_url(self):
        resposta = self.client.get(self.url, {"senha": SENHA_DO_BACKUP})

        self.assertNotIn("Content-Disposition", resposta)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(user=None)

        resposta = self.client.post(self.url, {"senha": SENHA_DO_BACKUP}, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pedidos_repetidos_sao_limitados(self):
        codigos = [
            self.client.post(self.url, {"senha": SENHA_DO_BACKUP}, format="json").status_code
            for _ in range(11)
        ]

        self.assertEqual(codigos[-1], status.HTTP_429_TOO_MANY_REQUESTS)


@override_settings(CACHES=CACHES_DE_TESTE)
class RelatoriosAPITests(APITestCase):
    """GET /api/ferramentas/exportar/, que ficou só com Excel, CSV e PDF."""

    def setUp(self):
        caches["throttle"].clear()
        self.user = User.objects.create_user(username="bia", password="senha-bem-comprida-123")
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api-ferramentas-exportar")

    def test_backup_por_get_foi_retirado(self):
        resposta = self.client.get(self.url, {"formato": "fcbk", "senha": SENHA_DO_BACKUP})

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            ConfigUsuario.objects.filter(usuario=self.user, ultimo_export_em__isnull=False).exists()
        )

    def test_relatorio_csv_continua_disponivel(self):
        resposta = self.client.get(self.url, {"formato": "csv"})

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_pedidos_repetidos_sao_limitados(self):
        codigos = [
            self.client.get(self.url, {"formato": "csv"}).status_code for _ in range(31)
        ]

        self.assertEqual(codigos[-1], status.HTTP_429_TOO_MANY_REQUESTS)
