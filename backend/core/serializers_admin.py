"""Serializers do painel administrativo.

Todos os campos são declarados **explicitamente**. Nenhum usa `fields = "__all__"`,
e isso é proposital: com `__all__`, adicionar um campo a um modelo o publicaria
automaticamente na API do painel, e é assim que um dado financeiro acabaria exposto
sem ninguém decidir expor.

O que o painel pode ver é metadado de conta. Nunca valor, saldo, ativo ou
transação — apenas contagens, para dar noção de volume de uso.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import LogAcaoAdmin

User = get_user_model()


class UsuarioAdminSerializer(serializers.ModelSerializer):
    """Representa uma conta na listagem do painel."""

    email_verificado = serializers.SerializerMethodField()
    total_lancamentos = serializers.IntegerField(read_only=True)
    total_ativos = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
            "email_verificado",
            "total_lancamentos",
            "total_ativos",
        ]
        read_only_fields = fields

    def get_email_verificado(self, obj) -> bool:
        """Informa se a conta já confirmou o endereço de e-mail.

        Returns:
            bool: True se houver `ConfigUsuario` com a confirmação registrada.
        """
        config = getattr(obj, "config", None)
        return bool(config and config.email_verificado)


class UsuarioAdminDetalheSerializer(UsuarioAdminSerializer):
    """Representa uma conta na tela de detalhe do painel."""

    email_verificado_em = serializers.DateTimeField(
        source="config.email_verificado_em", read_only=True, allow_null=True
    )
    moeda_padrao = serializers.CharField(
        source="config.moeda_padrao", read_only=True
    )

    class Meta(UsuarioAdminSerializer.Meta):
        fields = UsuarioAdminSerializer.Meta.fields + [
            "email_verificado_em",
            "moeda_padrao",
        ]
        read_only_fields = fields


class LogAcaoAdminSerializer(serializers.ModelSerializer):
    """Representa uma entrada do histórico de ações administrativas."""

    acao_display = serializers.CharField(source="get_acao_display", read_only=True)

    class Meta:
        model = LogAcaoAdmin
        fields = [
            "id",
            "ator_username",
            "alvo_username",
            "acao",
            "acao_display",
            "detalhe",
            "criada_em",
        ]
        read_only_fields = fields
