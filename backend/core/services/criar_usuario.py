"""Serviço de Inicialização e Criação de Contas de Usuário.

Este módulo encapsula as regras de negócio para criação de novos perfis no sistema,
garantindo que além da entidade de autenticação do Django, sejam inicializadas
as preferências individuais (ConfigUsuario) e as categorias financeiras padrão
de receitas, gastos e investimentos.
"""

from django.contrib.auth import get_user_model
from core.models import ConfigUsuario, Categoria

User = get_user_model()


def criar_usuario_com_ecosistema(username, senha):
    """Cria uma nova conta de usuário, inicializando suas configurações e categorias padrão.

    Garante integridade referencial ao criar de forma atômica o perfil, o
    registro de ConfigUsuario e as categorias financeiras essenciais do sistema.

    Args:
        username (str): Nome de usuário único para autenticação.
        senha (str): Senha do usuário em texto plano.

    Returns:
        User: A instância do usuário Django recém-criada.
    """
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

    return usuario

