from django.contrib.auth import get_user_model
from core.models import ConfigUsuario, Categoria, FormaPagamento, CategoriaCartao

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

    # Categorias de gasto MCC (globais - criadas apenas uma vez)
    _criar_categorias_cartao_padrao()

    return usuario


def _criar_categorias_cartao_padrao():
    """
    Cria as categorias de cartão (MCC) padrão do sistema.
    São globais (não pertencem a um usuário específico).
    Baseado no padrão ISO 18245 simplificado.
    """
    categorias_mcc = [
        ("0001", "Alimentação", "fa-utensils", "🍔"),
        ("0002", "Transporte", "fa-car", "🚗"),
        ("0003", "Moradia", "fa-house", "🏠"),
        ("0004", "Saúde", "fa-hospital", "🏥"),
        ("0005", "Educação", "fa-book", "📚"),
        ("0006", "Compras", "fa-bag-shopping", "🛍️"),
        ("0007", "Entretenimento", "fa-masks-theater", "🎭"),
        ("0008", "Viagens", "fa-plane", "✈️"),
        ("0009", "Serviços", "fa-wrench", "🔧"),
        ("0010", "Outros", "fa-tag", "📦"),
    ]

    for codigo, nome, icone, emoji in categorias_mcc:
        CategoriaCartao.objects.get_or_create(
            codigo=codigo,
            defaults={"nome": nome, "icone": icone, "emoji": emoji},
        )
