"""Testes unitários das classes de permissão.

`test_permissao_email_verificado.py` cobre o efeito via endpoints; aqui as classes
são exercitadas direto, porque duas fronteiras são difíceis de provocar por HTTP: o
último dia da carência ainda vale (um `<` no lugar de `<=` cortaria o acesso um dia
antes do prometido, e o teste de endpoint, feito com conta nova, continuaria
passando) e `IsAdminPlataforma` lê o banco, não a claim do JWT.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from core.models import ConfigUsuario
from core.permissions import EmailVerificadoOuCarencia, IsAdminPlataforma

User = get_user_model()


class _ViewFalsa:
    """Substituto de view: as duas permissões não inspecionam a view."""


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


class EmailVerificadoOuCarenciaTests(BasePermissaoTestCase):
    """Verifica o portão de importação e o período de carência."""

    def setUp(self):
        """Cria uma conta comum com e-mail ainda não confirmado."""
        super().setUp()
        self.permissao = EmailVerificadoOuCarencia()
        self.usuario = User.objects.create_user(
            username="joana", email="joana@exemplo.com", password="senha-comprida-123"
        )
        self.config, _ = ConfigUsuario.objects.get_or_create(usuario=self.usuario)

    def _envelhecer_conta(self, dias: int):
        """Recua a data de cadastro do usuário."""
        self.usuario.date_joined = timezone.now() - timedelta(days=dias)
        self.usuario.save(update_fields=["date_joined"])

    def test_recusa_usuario_anonimo(self):
        """Sem autenticação não há carência a conceder."""
        self.assertFalse(
            self.permissao.has_permission(
                self.requisicao_de(AnonymousUser()), self.view
            )
        )

    def test_permite_com_email_verificado(self):
        """E-mail confirmado dispensa qualquer contagem de prazo."""
        self.config.email_verificado = True
        self.config.save(update_fields=["email_verificado"])
        self._envelhecer_conta(365)

        self.assertTrue(
            self.permissao.has_permission(self.requisicao_de(self.usuario), self.view)
        )

    def test_permite_conta_recem_criada_sem_verificar(self):
        """O primeiro acesso funciona sem passar pela caixa de entrada."""
        self.assertTrue(
            self.permissao.has_permission(self.requisicao_de(self.usuario), self.view)
        )

    @override_settings(EMAIL_VERIFICATION_GRACE_DAYS=7)
    def test_permite_no_ultimo_dia_da_carencia(self):
        """O prazo prometido é inclusivo.

        Se a comparação virasse estrita, o acesso terminaria um dia antes do que
        a mensagem exibida ao usuário informa.
        """
        self._envelhecer_conta(6)

        self.assertTrue(
            self.permissao.has_permission(self.requisicao_de(self.usuario), self.view)
        )

    @override_settings(EMAIL_VERIFICATION_GRACE_DAYS=7)
    def test_recusa_apos_o_fim_da_carencia(self):
        """Passado o prazo, a confirmação vira obrigatória."""
        self._envelhecer_conta(8)

        self.assertFalse(
            self.permissao.has_permission(self.requisicao_de(self.usuario), self.view)
        )

    @override_settings(EMAIL_VERIFICATION_GRACE_DAYS=7)
    def test_conta_sem_email_recebe_mensagem_com_saida(self):
        """Quem não tem endereço não pode ser mandado confirmar um endereço.

        A mensagem padrão levaria a um beco sem saída: o reenvio de confirmação
        recusa a operação por não haver para onde enviar. A alternativa aponta
        para onde a pessoa resolve de fato — cadastrar o e-mail em Minha Conta.
        """
        sem_email = User.objects.create_user(
            username="antiga", password="senha-comprida-123"
        )
        ConfigUsuario.objects.get_or_create(usuario=sem_email)
        sem_email.date_joined = timezone.now() - timedelta(days=30)
        sem_email.save(update_fields=["date_joined"])

        permissao = EmailVerificadoOuCarencia()
        self.assertFalse(
            permissao.has_permission(self.requisicao_de(sem_email), self.view)
        )
        self.assertEqual(permissao.message, permissao.MENSAGEM_SEM_EMAIL)


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
