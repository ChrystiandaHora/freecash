from django.contrib.auth import get_user_model
from core.models import ConfigUsuario, Categoria, FormaPagamento

User = get_user_model()


def criar_usuario_com_ecosistema(username, senha):
    usuario = User.objects.create_user(username=username, password=senha)

    # Config do usuário
    ConfigUsuario.objects.get_or_create(usuario=usuario)

    # Categorias padrão
    Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Receita",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )
    Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Gastos",
        defaults={"tipo": Categoria.TIPO_DESPESA, "is_default": True},
    )
    Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Investimento",
        defaults={"tipo": Categoria.TIPO_INVESTIMENTO, "is_default": True},
    )

    # Formas de pagamento padrão (use usuario)
    FormaPagamento.objects.get_or_create(usuario=usuario, nome="PIX")
    FormaPagamento.objects.get_or_create(usuario=usuario, nome="Boleto")
    FormaPagamento.objects.get_or_create(usuario=usuario, nome="Cartão de Crédito")
    FormaPagamento.objects.get_or_create(usuario=usuario, nome="Cartão de Débito")

    return usuario
