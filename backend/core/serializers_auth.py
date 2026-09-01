"""Serializers dos fluxos de identidade: registro, verificação e senha."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.services.email_service import normalizar_email

User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    """Valida os dados de criação de uma nova conta."""

    username = serializers.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True)
    confirm = serializers.CharField(write_only=True)

    def validate_username(self, valor: str) -> str:
        valor = valor.strip()
        if User.objects.filter(username__iexact=valor).exists():
            raise serializers.ValidationError("Este nome de usuário já está em uso.")
        return valor

    def validate_email(self, valor: str) -> str:
        valor = normalizar_email(valor)
        if User.objects.filter(email__iexact=valor).exists():
            # Mensagem genérica para não revelar existência de cadastro
            raise serializers.ValidationError(
                "Não foi possível usar este e-mail. Se a conta é sua, "
                "tente recuperar o acesso pela opção de esqueci minha senha."
            )
        return valor

    def validate(self, dados: dict) -> dict:
        if dados["password"] != dados["confirm"]:
            raise serializers.ValidationError(
                {"confirm": "As senhas não coincidem."}
            )

        # Passar user provisório permite ao UserAttributeSimilarityValidator comparar campos
        usuario_provisorio = User(
            username=dados["username"], email=dados["email"]
        )
        try:
            validate_password(dados["password"], user=usuario_provisorio)
        except DjangoValidationError as erro:
            raise serializers.ValidationError({"password": list(erro.messages)})

        return dados


class EmailVerificacaoSerializer(serializers.Serializer):
    """Valida o par identificador/token do link de confirmação."""

    uid = serializers.CharField()
    token = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Valida o pedido de redefinição de senha."""

    email = serializers.EmailField(max_length=254)

    def validate_email(self, valor: str) -> str:
        return normalizar_email(valor)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Valida confirmação de redefinição de senha."""

    uid = serializers.CharField()
    token = serializers.CharField()
    nova_senha = serializers.CharField(write_only=True)
    confirmar = serializers.CharField(write_only=True)

    def validate(self, dados: dict) -> dict:
        if dados["nova_senha"] != dados["confirmar"]:
            raise serializers.ValidationError(
                {"confirmar": "As senhas não coincidem."}
            )
        return dados

