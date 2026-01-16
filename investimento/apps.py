from django.apps import AppConfig


class InvestimentoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "investimento"

    def ready(self):
        import investimento.signals
