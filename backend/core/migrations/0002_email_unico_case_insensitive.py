"""Torna o e-mail um identificador único, sem trocar o AUTH_USER_MODEL.

`auth.User.email` é declarado `blank=True` e sem unicidade, e não é possível
adicionar `Meta.constraints` a um modelo de aplicativo terceiro. A unicidade é
então imposta em duas camadas: validação no serializer de registro (mensagem
amigável) e este índice no banco (garantia real, à prova de concorrência).

Esta migration não é absorvida pela `0001_initial` porque `makemigrations` só
gera operações derivadas dos modelos do projeto, e o índice abaixo é SQL cru
sobre `auth_user`. Removê-la deixaria a unicidade de e-mail existindo apenas no
serializer, sem garantia no banco.

Três decisões carregam peso aqui:

1. **Índice sobre `LOWER(email)`** — sem isso, `Ana@x.com` e `ana@x.com` seriam
   endereços distintos, e o fluxo de redefinição de senha ficaria ambíguo.

2. **Índice parcial (`WHERE email <> ''`)** — `createsuperuser --noinput` não
   exige e-mail, e contas de serviço podem não ter um. Um índice único total
   trataria todas as strings vazias como duplicatas e impediria a criação de
   qualquer conta sem e-mail.

3. **Falhar em vez de adivinhar** — se a normalização revelar dois usuários que
   passam a colidir, a migration aborta com a lista dos conflitos. Escolher
   automaticamente quem fica com o endereço perderia o acesso de alguém à sua
   própria conta; a decisão é humana. Em banco novo o passo é um no-op.
"""

from django.db import migrations


def normalizar_emails(apps, schema_editor):
    """Reduz os e-mails existentes a minúsculas, abortando se isso criar colisão.

    Args:
        apps (Apps): Registro de modelos na versão desta migration.
        schema_editor (BaseDatabaseSchemaEditor): Editor de esquema em uso.

    Raises:
        RuntimeError: Se dois ou mais usuários passarem a compartilhar o mesmo
            endereço após a normalização.
    """
    User = apps.get_model("auth", "User")

    duplicados = {}
    for usuario in User.objects.exclude(email="").only("id", "email"):
        chave = usuario.email.strip().lower()
        duplicados.setdefault(chave, []).append(usuario.id)

    conflitos = {
        email: ids for email, ids in duplicados.items() if len(ids) > 1
    }
    if conflitos:
        detalhe = "; ".join(
            f"{email} -> ids {sorted(ids)}" for email, ids in sorted(conflitos.items())
        )
        raise RuntimeError(
            "Não é possível tornar o e-mail único: os endereços abaixo ficariam "
            "duplicados após a normalização para minúsculas. Resolva manualmente "
            f"antes de aplicar esta migration. Conflitos: {detalhe}"
        )

    for usuario in User.objects.exclude(email="").only("id", "email"):
        normalizado = usuario.email.strip().lower()
        if normalizado != usuario.email:
            usuario.email = normalizado
            usuario.save(update_fields=["email"])


def reverter_normalizacao(apps, schema_editor):
    """Não faz nada: a caixa original dos e-mails não é recuperável.

    Args:
        apps (Apps): Registro de modelos na versão desta migration.
        schema_editor (BaseDatabaseSchemaEditor): Editor de esquema em uso.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(normalizar_emails, reverter_normalizacao),
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_lower_uniq "
                "ON auth_user (LOWER(email)) WHERE email <> '';"
            ),
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_lower_uniq;",
        ),
    ]
