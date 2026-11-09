"""Cria as categorias sugeridas para os usuários que já existiam.

A lista é uma cópia congelada de `CATEGORIAS_SUGERIDAS` na data desta migration:
importar a constante faria a migration mudar de efeito quando a lista mudasse.
"""

from django.conf import settings
from django.db import migrations

DESPESA = "D"
RECEITA = "R"

CATEGORIAS = {
    DESPESA: (
        "Moradia", "Contas da casa", "Mercado", "Alimentação fora", "Transporte",
        "Saúde", "Educação", "Lazer", "Assinaturas", "Compras e vestuário",
        "Cuidados pessoais", "Pets", "Impostos e taxas", "Seguros",
        "Dívidas e empréstimos", "Presentes e doações", "Viagem", "Outras despesas",
    ),
    RECEITA: (
        "Salário", "13º e férias", "Freelance", "Pró-labore", "Aluguel recebido",
        "Rendimentos", "Reembolso", "Presentes recebidos", "Outras receitas",
    ),
}


def criar_para_usuarios_existentes(apps, schema_editor):
    """Cria as categorias que faltam; as que o usuário já tem ficam como estão."""
    Categoria = apps.get_model("core", "Categoria")
    Usuario = apps.get_model(settings.AUTH_USER_MODEL)

    for usuario_id in Usuario.objects.values_list("id", flat=True):
        existentes = set(
            Categoria.objects.filter(usuario_id=usuario_id).values_list("nome", flat=True)
        )
        novas = [
            Categoria(usuario_id=usuario_id, nome=nome, tipo=tipo)
            for tipo, nomes in CATEGORIAS.items()
            for nome in nomes
            if nome not in existentes
        ]
        Categoria.objects.bulk_create(novas)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_evento_conta_evento"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    # Sem reverso destrutivo: apagar por nome levaria junto categorias já em uso
    operations = [
        migrations.RunPython(criar_para_usuarios_existentes, migrations.RunPython.noop),
    ]
