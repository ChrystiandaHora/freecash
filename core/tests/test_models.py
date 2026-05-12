from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Categoria, Conta, CartaoCredito, ConfigUsuario
from datetime import timedelta
from decimal import Decimal

class CoreModelsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.categoria_receita = Categoria.objects.create(
            usuario=self.user, nome="Salário", tipo=Categoria.TIPO_RECEITA
        )
        self.categoria_despesa = Categoria.objects.create(
            usuario=self.user, nome="Aluguel", tipo=Categoria.TIPO_DESPESA
        )

    def test_categoria_str(self):
        self.assertEqual(str(self.categoria_receita), "Salário")

    def test_conta_marcar_realizada(self):
        conta = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_RECEITA,
            descricao="Freelance",
            valor=Decimal("1000.00"),
            data_prevista=timezone.localdate(),
            categoria=self.categoria_receita
        )
        self.assertFalse(conta.transacao_realizada)
        self.assertIsNone(conta.data_realizacao)

        conta.marcar_realizada()
        self.assertTrue(conta.transacao_realizada)
        self.assertEqual(conta.data_realizacao, timezone.localdate())

    def test_conta_desmarcar_realizada(self):
        conta = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Lanche",
            valor=Decimal("25.00"),
            data_prevista=timezone.localdate(),
            transacao_realizada=True,
            data_realizacao=timezone.localdate(),
            categoria=self.categoria_despesa
        )
        conta.desmarcar_realizada()
        self.assertFalse(conta.transacao_realizada)
        self.assertIsNone(conta.data_realizacao)

    def test_conta_esta_atrasada(self):
        # Atrasada: data_prevista no passado e não realizada
        conta_atrasada = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Internet",
            valor=Decimal("100.00"),
            data_prevista=timezone.localdate() - timedelta(days=1),
            transacao_realizada=False
        )
        self.assertTrue(conta_atrasada.esta_atrasada)

        # Não atrasada: data_prevista no futuro
        conta_futura = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Internet Futura",
            valor=Decimal("100.00"),
            data_prevista=timezone.localdate() + timedelta(days=1),
            transacao_realizada=False
        )
        self.assertFalse(conta_futura.esta_atrasada)

        # Não atrasada: já realizada (mesmo que a data prevista tenha passado)
        conta_realizada = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Internet Paga",
            valor=Decimal("100.00"),
            data_prevista=timezone.localdate() - timedelta(days=1),
            transacao_realizada=True,
            data_realizacao=timezone.localdate()
        )
        self.assertFalse(conta_realizada.esta_atrasada)

    def test_cartao_credito_str(self):
        cartao = CartaoCredito.objects.create(
            usuario=self.user,
            nome="Nubank",
            ultimos_digitos="1234"
        )
        self.assertEqual(str(cartao), "Nubank ****1234")

    def test_config_usuario_str(self):
        config, created = ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.assertEqual(str(config), f"Configurações de {self.user.username}")
