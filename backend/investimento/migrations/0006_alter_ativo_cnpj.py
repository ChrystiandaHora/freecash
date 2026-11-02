# Separada da 0005: no PostgreSQL, UPDATE e ALTER TABLE na mesma transação podem
# falhar com "pending trigger events" por causa das FKs adiadas do Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investimento', '0005_ativo_cnpj_nulo_para_vazio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ativo',
            name='cnpj',
            field=models.CharField(blank=True, help_text='Somente números (14 dígitos) para atualização via CVM', max_length=14, verbose_name='CNPJ do Fundo'),
        ),
    ]
