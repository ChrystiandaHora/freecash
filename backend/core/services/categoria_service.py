"""Resolução de categoria a partir do nome digitado nos formulários de lançamento."""

from core.models import Categoria


def resolver_categoria_por_nome(usuario, nome: str, tipo: str) -> Categoria:
    """Busca a categoria do usuário pelo nome, criando-a com `tipo` se não existir.

    O nome identifica a categoria (`unique_together = ("usuario", "nome")`), então o
    tipo só vale para a criação. Buscar por nome e tipo falhava quando o nome já
    existia com outro tipo — a "Investimento" padrão numa despesa — e o `create`
    seguinte violava a restrição única, devolvendo 500.

    Args:
        usuario: Dono da categoria.
        nome: Nome informado no lançamento; espaços nas pontas são ignorados.
        tipo: Tipo da categoria, se for preciso criá-la.

    Returns:
        Categoria: A categoria existente ou a recém-criada.
    """
    categoria, _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome=nome.strip(),
        defaults={"tipo": tipo},
    )
    return categoria
