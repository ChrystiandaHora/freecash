"""Testes do serviço de envio de e-mails transacionais.

Duas garantias justificam estes testes, e as duas são invisíveis olhando só a
assinatura das funções:

**O e-mail nunca sai antes do commit.** O envio é agendado com
`transaction.on_commit`. Sem isso, um erro posterior dentro do `atomic` desfaria a
criação da conta e o usuário receberia, ainda assim, um e-mail confirmando uma
conta inexistente, com um link que jamais funcionaria.

**A falha de envio não derruba a requisição.** Se o servidor de e-mail estiver
fora do ar, o cadastro precisa ser concluído: a conta existe, e todo fluxo oferece
"reenviar" como recuperação.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from django.test import TestCase, override_settings

from core.models import ConfigUsuario
from core.services.email_service import (
    enviar_reset_senha,
    enviar_verificacao_email,
    normalizar_email,
)

User = get_user_model()


class NormalizarEmailTests(TestCase):
    """Cobre a normalização canônica de endereços."""

    def test_normaliza_caixa_e_espacos(self):
        """A forma canônica é o que casa com o índice único sobre LOWER(email)."""
        self.assertEqual(normalizar_email("  Ana@Exemplo.COM "), "ana@exemplo.com")

    def test_tolera_vazio_e_nulo(self):
        """Contas sem e-mail existem: o superusuário criado por linha de comando."""
        self.assertEqual(normalizar_email(""), "")
        self.assertEqual(normalizar_email(None), "")


@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_BASE_URL="https://app.exemplo.com",
)
class EnvioDeEmailTests(TestCase):
    """Cobre a montagem e o despacho das mensagens."""

    def setUp(self):
        """Cria um usuário com configuração associada."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)

    def test_verificacao_monta_texto_e_html(self):
        """A mensagem sai com corpo em texto e alternativa em HTML."""
        with self.captureOnCommitCallbacks(execute=True):
            enviar_verificacao_email(self.user)

        self.assertEqual(len(mail.outbox), 1)
        mensagem = mail.outbox[0]
        self.assertEqual(mensagem.to, ["ana@exemplo.com"])
        self.assertIn("https://app.exemplo.com/verificar-email/", mensagem.body)

        tipos = [tipo for _, tipo in mensagem.alternatives]
        self.assertIn("text/html", tipos)
        html = next(c for c, t in mensagem.alternatives if t == "text/html")
        self.assertIn("https://app.exemplo.com/verificar-email/", html)

    def test_reset_monta_link_para_o_spa(self):
        """O link aponta para o frontend, nunca para o endpoint da API."""
        with self.captureOnCommitCallbacks(execute=True):
            enviar_reset_senha(self.user, "token-de-teste")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "https://app.exemplo.com/redefinir-senha/", mail.outbox[0].body
        )
        self.assertIn("token-de-teste", mail.outbox[0].body)

    def test_destinatario_vazio_nao_envia(self):
        """Conta sem e-mail cadastrado não gera mensagem sem destino."""
        self.user.email = ""
        self.user.save(update_fields=["email"])

        with self.captureOnCommitCallbacks(execute=True):
            enviar_verificacao_email(self.user)

        self.assertEqual(len(mail.outbox), 0)

    def test_nada_e_enviado_se_a_transacao_for_desfeita(self):
        """Prova o agendamento por on_commit.

        Sem `transaction.on_commit`, este teste enviaria o e-mail mesmo com o
        rollback — e em produção o usuário receberia confirmação de uma conta que
        deixou de existir.
        """
        class ErroDeTeste(Exception):
            """Exceção usada para forçar o rollback."""

        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    enviar_verificacao_email(self.user)
                    raise ErroDeTeste()
            except ErroDeTeste:
                pass

        self.assertEqual(len(mail.outbox), 0)

    def test_falha_de_envio_nao_propaga_excecao(self):
        """Servidor de e-mail fora do ar não pode derrubar o cadastro."""
        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=OSError("SMTP indisponível"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                # Não deve levantar: a falha vai para o log.
                enviar_verificacao_email(self.user)

    @override_settings(EMAIL_ASYNC=True)
    def test_modo_assincrono_despacha_em_thread(self):
        """Em produção o envio sai do caminho da requisição."""
        with mock.patch("threading.Thread") as thread:
            with self.captureOnCommitCallbacks(execute=True):
                enviar_verificacao_email(self.user)

        thread.assert_called_once()
        # daemon=False para que o processo não seja reciclado no meio do envio.
        self.assertIs(thread.call_args.kwargs["daemon"], False)
        thread.return_value.start.assert_called_once()
