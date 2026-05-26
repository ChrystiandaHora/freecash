"""Configuração da Aplicação de Investimentos no Ecossistema Django.

Define as classes de inicialização e registros de hooks/signals para o correto acoplamento
da gestão de carteiras financeiras.
"""

from django.apps import AppConfig


class InvestimentoConfig(AppConfig):
    """Classe de configuração do módulo de Investimento.

    Responsável por definir o tipo de campo autoincrementável padrão e gerenciar
    a importação síncrona dos signals de banco de dados no carregamento do Django.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "investimento"

    def ready(self):
        """Executa rotinas de inicialização assim que o registro de aplicações do Django é concluído.

        Registra os receptores de sinais de banco de dados (signals.py) no barramento do Django.
        """
        import investimento.signals

