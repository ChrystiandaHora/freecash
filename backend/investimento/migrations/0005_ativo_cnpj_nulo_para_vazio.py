from django.db import migrations


def nulos_para_vazio(apps, schema_editor):
    """Converte CNPJ nulo em vazio antes de o campo deixar de aceitar NULL (0006).

    O código já tratava `None` e `""` igual (`if ativo.cnpj`, `exclude(cnpj__isnull=True)
    .exclude(cnpj="")`), então a troca não muda o que o usuário vê.
    """
    Ativo = apps.get_model("investimento", "Ativo")
    Ativo.objects.filter(cnpj__isnull=True).update(cnpj="")


class Migration(migrations.Migration):

    dependencies = [
        ('investimento', '0004_ativo_tipo_fiscal'),
    ]

    operations = [
        migrations.RunPython(nulos_para_vazio, migrations.RunPython.noop),
    ]
