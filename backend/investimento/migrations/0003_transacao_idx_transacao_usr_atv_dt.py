# Generated manually for performance index optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investimento', '0002_ativo_historico_verificado_em'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='transacao',
            index=models.Index(
                fields=['usuario', 'ativo', 'data'],
                name='idx_transacao_usr_atv_dt',
            ),
        ),
    ]

