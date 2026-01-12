from django.contrib.auth import get_user_model
from core.models import ConfigUsuario, Categoria, FormaPagamento

User = get_user_model()


def criar_usuario_com_ecosistema(username, senha):
    usuario = User.objects.create_user(username=username, password=senha)

    # Config do usuário (no seu model, created_by é OneToOne e é o dono)
    ConfigUsuario.objects.get_or_create(created_by=usuario)

    # Categorias padrão (use created_by, não usuario)
    Categoria.objects.get_or_create(
        created_by=usuario,
        nome="Receita",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )
    Categoria.objects.get_or_create(
        created_by=usuario,
        nome="Gastos",
        defaults={"tipo": Categoria.TIPO_DESPESA, "is_default": True},
    )
    Categoria.objects.get_or_create(
        created_by=usuario,
        nome="Investimento",
        defaults={"tipo": Categoria.TIPO_INVESTIMENTO, "is_default": True},
    )

    # Formas de pagamento padrão (use created_by, não usuario)
    FormaPagamento.objects.get_or_create(created_by=usuario, nome="PIX")
    FormaPagamento.objects.get_or_create(created_by=usuario, nome="Boleto")
    FormaPagamento.objects.get_or_create(created_by=usuario, nome="Cartão de Crédito")
    FormaPagamento.objects.get_or_create(created_by=usuario, nome="Cartão de Débito")

    return usuario
