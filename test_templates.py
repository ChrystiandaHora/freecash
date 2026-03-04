import os
import django
from django.template.loader import render_to_string

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freecash.settings")
django.setup()

templates_to_test = [
    "investimento/transacoes/transacao_form.html",
    "core/servicos/conciliacao_upload.html",
]

for t in templates_to_test:
    try:
        render_to_string(t)
        print(f"✅ {t} rendered successfully (or at least loaded).")
    except Exception as e:
        print(f"❌ Error rendering {t}: {type(e).__name__} - {e}")
