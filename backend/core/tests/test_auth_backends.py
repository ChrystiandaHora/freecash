"""Testes do backend que aceita e-mail ou nome de usuário no login.

`EmailOuUsernameBackend` está registrado em `AUTHENTICATION_BACKENDS` e decide
todo login do produto, mas não tinha teste algum. Três propriedades sustentam o
que é verificado aqui:

**O e-mail resolve independentemente da caixa.** O índice único do banco é sobre
`LOWER(email)`, então `Ana@Exemplo.com` e `ana@exemplo.com` são o mesmo endereço.
Se o backend comparasse com distinção de maiúsculas, existiria um endereço que
passa no cadastro e falha no login — sem mensagem que explicasse por quê.

**O fallback por username não pode sumir.** É o que mantém o superusuário
entrando, e ele pode nem ter e-mail cadastrado.

**Conta suspensa não autentica.** `user_can_authenticate` é o ponto onde a
suspensão administrativa vira recusa de login; sem teste, uma refatoração que
retornasse o usuário antes dessa checagem passaria despercebida.
"""

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase

from core.auth_backends import EmailOuUsernameBackend

User = get_user_model()

SENHA = "senha-bem-comprida-123"


class EmailOuUsernameBackendTests(TestCase):
    """Verifica a resolução do identificador e as recusas de autenticação."""

    def setUp(self):
        """Cria uma conta comum com e-mail em minúsculas."""
        self.usuario = User.objects.create_user(
            username="joana",
            email="joana@exemplo.com",
            password=SENHA,
        )

    def test_autentica_pelo_email(self):
        """O e-mail cadastrado é aceito como identificador."""
        self.assertEqual(
            authenticate(username="joana@exemplo.com", password=SENHA),
            self.usuario,
        )

    def test_autentica_pelo_email_ignorando_caixa(self):
        """A caixa do endereço não altera o resultado.

        O banco garante unicidade sobre LOWER(email); a comparação aqui precisa
        seguir a mesma regra, senão o cadastro aceita um endereço que o login
        recusa.
        """
        self.assertEqual(
            authenticate(username="Joana@Exemplo.COM", password=SENHA),
            self.usuario,
        )

    def test_autentica_pelo_username(self):
        """O nome de usuário continua sendo um identificador válido."""
        self.assertEqual(
            authenticate(username="joana", password=SENHA), self.usuario
        )

    def test_ignora_espacos_em_volta_do_identificador(self):
        """Espaço colado pelo preenchimento automático não impede o login."""
        self.assertEqual(
            authenticate(username="  joana@exemplo.com  ", password=SENHA),
            self.usuario,
        )

    def test_aceita_identificador_na_chave_email(self):
        """O backend também lê o identificador vindo em `email=`.

        `authenticate()` é chamado com nomes de campo diferentes conforme o
        formulário de origem; o backend precisa aceitar os dois.
        """
        backend = EmailOuUsernameBackend()
        self.assertEqual(
            backend.authenticate(None, email="joana@exemplo.com", password=SENHA),
            self.usuario,
        )

    def test_recusa_senha_incorreta(self):
        """Identificador válido com senha errada não autentica."""
        self.assertIsNone(
            authenticate(username="joana@exemplo.com", password="outra-senha-123")
        )

    def test_recusa_identificador_inexistente(self):
        """Endereço sem conta não autentica."""
        self.assertIsNone(
            authenticate(username="ninguem@exemplo.com", password=SENHA)
        )

    def test_recusa_conta_suspensa(self):
        """Conta com `is_active=False` não autentica, mesmo com a senha certa.

        É assim que a suspensão pelo painel administrativo impede um novo login;
        a revogação dos tokens cuida das sessões já abertas.
        """
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])

        self.assertIsNone(
            authenticate(username="joana@exemplo.com", password=SENHA)
        )

    def test_recusa_sem_senha(self):
        """Sem senha não há o que verificar."""
        backend = EmailOuUsernameBackend()
        self.assertIsNone(backend.authenticate(None, username="joana", password=None))

    def test_recusa_sem_identificador(self):
        """Sem identificador não há quem procurar."""
        backend = EmailOuUsernameBackend()
        self.assertIsNone(backend.authenticate(None, username=None, password=SENHA))

    def test_username_com_arroba_cai_no_fallback(self):
        """Um username que contém @ ainda autentica quando não é e-mail de ninguém.

        O backend decide pela presença de @ se tenta o e-mail primeiro. Quando essa
        busca não encontra nada, a tentativa por username precisa acontecer mesmo
        assim — do contrário, contas antigas com @ no nome ficariam trancadas.
        """
        peculiar = User.objects.create_user(username="ana@casa", password=SENHA)

        self.assertEqual(
            authenticate(username="ana@casa", password=SENHA), peculiar
        )
