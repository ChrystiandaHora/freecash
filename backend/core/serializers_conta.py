"""Serializers das operações de gerenciamento de conta (perfil, e-mail, senha e exclusão)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.services.email_service import normalizar_email

User = get_user_model()


class SenhaAtualMixin(serializers.Serializer):
    """Mixin que valida a senha atual do usuário autenticado para ações sensíveis."""

    senha_atual = serializers.CharField(write_only=True)

    def validate_senha_atual(self, valor: str) -> str:
        usuario = self.context["request"].user
        if not usuario.check_password(valor):
            raise serializers.ValidationError("Senha atual incorreta.")
        return valor


class PerfilUpdateSerializer(serializers.Serializer):
    """Valida a edição de preferências e nome de usuário."""

    username = serializers.CharField(
        max_length=150, required=False, validators=[UnicodeUsernameValidator()]
    )
    moeda_padrao = serializers.CharField(max_length=10, required=False)

    def validate_username(self, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("Informe um nome de usuário.")

        usuario = self.context["request"].user
        conflito = (
            User.objects.filter(username__iexact=valor)
            .exclude(pk=usuario.pk)
            .exists()
        )
        if conflito:
            raise serializers.ValidationError("Este nome de usuário já está em uso.")
        return valor

    def validate_moeda_padrao(self, valor: str) -> str:
        valor = valor.strip().upper()
        if not valor:
            raise serializers.ValidationError("Informe a moeda padrão.")
        return valor


class TrocaEmailSerializer(SenhaAtualMixin):
    """Valida o pedido de troca de endereço de e-mail."""

    novo_email = serializers.EmailField(max_length=254)

    def validate_novo_email(self, valor: str) -> str:
        valor = normalizar_email(valor)
        usuario = self.context["request"].user

        if valor == normalizar_email(usuario.email):
            raise serializers.ValidationError(
                "Este já é o e-mail da sua conta."
            )

        conflito = (
            User.objects.filter(email__iexact=valor)
            .exclude(pk=usuario.pk)
            .exists()
        )
        if conflito:
            raise serializers.ValidationError(
                "Não foi possível usar este e-mail."
            )
        return valor


class TrocaSenhaSerializer(SenhaAtualMixin):
    """Valida a troca de senha com o usuário já autenticado."""

    nova_senha = serializers.CharField(write_only=True)
    confirmar = serializers.CharField(write_only=True)

    def validate(self, dados: dict) -> dict:
        if dados["nova_senha"] != dados["confirmar"]:
            raise serializers.ValidationError(
                {"confirmar": "As senhas não coincidem."}
            )

        if dados["nova_senha"] == dados["senha_atual"]:
            raise serializers.ValidationError(
                {"nova_senha": "A nova senha precisa ser diferente da atual."}
            )

        usuario = self.context["request"].user
        try:
            validate_password(dados["nova_senha"], user=usuario)
        except DjangoValidationError as erro:
            raise serializers.ValidationError(
                {"nova_senha": list(erro.messages)}
            )

        return dados


class ExclusaoContaSerializer(SenhaAtualMixin):
    """Valida a exclusão definitiva da conta (exige senha e confirmação por username)."""

    confirmacao = serializers.CharField()

    def validate_confirmacao(self, valor: str) -> str:
        usuario = self.context["request"].user
        if valor.strip() != usuario.get_username():
            raise serializers.ValidationError(
                "Digite exatamente o seu nome de usuário para confirmar."
            )
        return valor

