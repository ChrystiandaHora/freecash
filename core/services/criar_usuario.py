from django.contrib.auth.models import User
from core.models import ConfigUsuario, Categoria


def criar_usuario_com_ecosistema(username, senha):
    # Cria o usuário
    usuario = User.objects.create_user(username=username, password=senha)

    # Config do usuário
    ConfigUsuario.objects.create(usuario=usuario)

    # Categorias padrão
    Categoria.objects.create(
        usuario=usuario,
        nome="Receita agregada",
        tipo=Categoria.TIPO_RECEITA,
        is_default=True,
    )

    Categoria.objects.create(
        usuario=usuario,
        nome="Outras receitas agregadas",
        tipo=Categoria.TIPO_RECEITA,
        is_default=True,
    )

    Categoria.objects.create(
        usuario=usuario,
        nome="Gastos agregados",
        tipo=Categoria.TIPO_DESPESA,
        is_default=True,
    )

    return usuario
