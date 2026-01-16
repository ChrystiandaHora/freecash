import uuid
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freecash.settings")
django.setup()

from core.models import Categoria, FormaPagamento, Conta, ConfigUsuario, LogImportacao
from investimento.models import Ativo, ClasseAtivo, Transacao

models_list = [
    Categoria,
    FormaPagamento,
    Conta,
    ConfigUsuario,
    LogImportacao,
    Ativo,
    ClasseAtivo,
    Transacao,
]

for model in models_list:
    try:
        count = 0
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save()
            count += 1
        print(f"Populated {count} UUIDs for {model.__name__}")
    except Exception as e:
        print(f"Error populating {model.__name__}: {e}")
