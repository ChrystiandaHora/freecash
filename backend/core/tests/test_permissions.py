"""Testes unitários das classes de permissão.

A classe é exercitada direto, porque a fronteira que importa é difícil de provocar por
HTTP: `IsAdminPlataforma` lê o banco, não a claim do JWT.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from core.permissions import IsAdminPlataforma

User = get_user_model()


class _ViewFalsa:
    """Substituto de view: a permissão não inspeciona a view."""


class BasePermissaoTestCase(TestCase):
    """Infraestrutura comum: fábrica de requisições com usuário anexado."""

    def setUp(self):
        """Prepara a fábrica de requisições."""
        self.factory = APIRequestFactory()
        self.view = _ViewFalsa()

    def requisicao_de(self, usuario):
        """Monta uma requisição autenticada como o usuário informado.

        Returns:
            HttpRequest: Requisição com `user` preenchido.
        """
        requisicao = self.factory.post("/api/ferramentas/importar/")
        requisicao.user = usuario
        return requisicao


class IsAdminPlataformaTests(BasePermissaoTestCase):
    """Verifica o portão do painel administrativo."""

    def setUp(self):
        """Cria um administrador e um usuário comum."""
        super().setUp()
        self.permissao = IsAdminPlataforma()
        self.admin = User.objects.create_user(
            username="admin", password="senha-comprida-123", is_staff=True
        )
        self.comum = User.objects.create_user(
            username="joana", password="senha-comprida-123"
        )

    def test_permite_administrador_ativo(self):
        """`is_staff` com conta ativa é o critério de acesso."""
        self.assertTrue(
            self.permissao.has_permission(self.requisicao_de(self.admin), self.view)
        )

    def test_recusa_usuario_comum(self):
        """Conta sem `is_staff` não acessa o painel."""
        self.assertFalse(
            self.permissao.has_permission(self.requisicao_de(self.comum), self.view)
        )

    def test_recusa_anonimo(self):
        """Sem autenticação, não há papel a avaliar."""
        self.assertFalse(
            self.permissao.has_permission(
                self.requisicao_de(AnonymousUser()), self.view
            )
        )

    def test_recusa_administrador_suspenso(self):
        """Suspender um administrador tira o acesso na mesma requisição.

        `is_active` é checado explicitamente para que a suspensão não dependa de
        o token ser renovado.
        """
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        self.assertFalse(
            self.permissao.has_permission(self.requisicao_de(self.admin), self.view)
        )
