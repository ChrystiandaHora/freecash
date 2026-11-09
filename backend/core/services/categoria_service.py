"""Resolução de categoria a partir do nome digitado nos formulários de lançamento."""

from core.models import Categoria

# "Cartão de Crédito" fica de fora: diz como foi pago, não com o quê
CATEGORIAS_SUGERIDAS = {
    Categoria.TIPO_DESPESA: (
        "Moradia",
        "Contas da casa",
        "Mercado",
        "Alimentação fora",
        "Transporte",
        "Saúde",
        "Educação",
        "Lazer",
        "Assinaturas",
        "Compras e vestuário",
        "Cuidados pessoais",
        "Pets",
        "Impostos e taxas",
        "Seguros",
        "Dívidas e empréstimos",
        "Presentes e doações",
        "Viagem",
        "Outras despesas",
    ),
    Categoria.TIPO_RECEITA: (
        "Salário",
        "13º e férias",
        "Freelance",
        "Pró-labore",
        "Aluguel recebido",
        "Rendimentos",
        "Reembolso",
        "Presentes recebidos",
        "Outras receitas",
    ),
}


def criar_categorias_sugeridas(usuario) -> None:
    """Garante que o usuário tenha as categorias de `CATEGORIAS_SUGERIDAS`.

    São as opções que o formulário de lançamento sugere. Ficam com
    `is_default=False` porque o lançamento em lote toma a primeira categoria de
    despesa com `is_default=True` como reserva, e essa tem de continuar sendo
    "Gastos". Uma categoria que o usuário já tenha com o mesmo nome é mantida como
    está, inclusive o tipo: o nome é único por usuário.

    Args:
        usuario: Dono das categorias.
    """
    for tipo, nomes in CATEGORIAS_SUGERIDAS.items():
        for nome in nomes:
            Categoria.objects.get_or_create(
                usuario=usuario, nome=nome, defaults={"tipo": tipo},
            )


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
