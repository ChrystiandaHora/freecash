"""Serializers dos fluxos de identidade: registro, verificação e senha.

O registro era validado à mão dentro da view, com mínimo próprio de 6 caracteres e
sem chamar `validate_password` — então os `AUTH_PASSWORD_VALIDATORS` do settings,
inclusive o que impede senha parecida com o nome de usuário, nunca rodavam.

Uma assimetria deliberada nas mensagens: dizer que um **nome de usuário** já existe é
inevitável, porque a tela de login revela o mesmo. Já confirmar que um **e-mail** está
cadastrado entregaria quem tem conta aqui — associação sensível num sistema
financeiro. Por isso o erro de e-mail duplicado é genérico.
"""

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
        """Normaliza e garante que o nome de usuário esteja livre.

        Returns:
            str: Nome de usuário sem espaços nas bordas.

        Raises:
            serializers.ValidationError: Se o nome já estiver em uso.
        """
        valor = valor.strip()
        if User.objects.filter(username__iexact=valor).exists():
            raise serializers.ValidationError("Este nome de usuário já está em uso.")
        return valor

    def validate_email(self, valor: str) -> str:
        """Normaliza o endereço e recusa duplicatas sem confirmar a existência.

        Returns:
            str: Endereço normalizado.

        Raises:
            serializers.ValidationError: Se o endereço não puder ser usado. A
                mensagem é intencionalmente genérica para não revelar quem já tem
                conta no sistema.
        """
        valor = normalizar_email(valor)
        if User.objects.filter(email__iexact=valor).exists():
            raise serializers.ValidationError(
                "Não foi possível usar este e-mail. Se a conta é sua, "
                "tente recuperar o acesso pela opção de esqueci minha senha."
            )
        return valor

    def validate(self, dados: dict) -> dict:
        """Confere a confirmação de senha e aplica os validadores do Django.

        Returns:
            dict: Os mesmos dados, se válidos.

        Raises:
            serializers.ValidationError: Se as senhas divergirem ou a senha for
                reprovada por algum dos AUTH_PASSWORD_VALIDATORS.
        """
        if dados["password"] != dados["confirm"]:
            raise serializers.ValidationError(
                {"confirm": "As senhas não coincidem."}
            )

        # Passar o `user` é o que permite ao UserAttributeSimilarityValidator
        # comparar a senha com o nome de usuário e o e-mail. Sem ele, o validador
        # está configurado mas não tem nada com que comparar.
        usuario_provisorio = User(
            username=dados["username"], email=dados["email"]
        )
        try:
            validate_password(dados["password"], user=usuario_provisorio)
        except DjangoValidationError as erro:
            raise serializers.ValidationError({"password": list(erro.messages)})

        return dados


class EmailVerificacaoSerializer(serializers.Serializer):
    """Valida o par identificador/token vindo do link de confirmação."""

    uid = serializers.CharField()
    token = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Valida o pedido de redefinição de senha."""

    email = serializers.EmailField(max_length=254)

    def validate_email(self, valor: str) -> str:
        """Normaliza o endereço para casar com o armazenado.

        Returns:
            str: Endereço normalizado.
        """
        return normalizar_email(valor)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Valida a redefinição de senha propriamente dita.

    A força da nova senha é verificada aqui apenas quanto à confirmação; a validação
    contra os `AUTH_PASSWORD_VALIDATORS` acontece na view, que é onde o usuário já
    foi resolvido a partir do token e pode ser passado a `validate_password`.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    nova_senha = serializers.CharField(write_only=True)
    confirmar = serializers.CharField(write_only=True)

    def validate(self, dados: dict) -> dict:
        """Confere se as duas senhas informadas coincidem.

        Returns:
            dict: Os mesmos dados, se válidos.

        Raises:
            serializers.ValidationError: Se as senhas divergirem.
        """
        if dados["nova_senha"] != dados["confirmar"]:
            raise serializers.ValidationError(
                {"confirmar": "As senhas não coincidem."}
            )
        return dados
