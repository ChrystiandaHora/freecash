"""Serializers das operações que o usuário faz sobre a própria conta.

Três das quatro operações aqui — trocar e-mail, trocar senha e excluir a conta —
exigem a **senha atual**. Não é burocracia: quem toma uma sessão aberta (uma
máquina destravada, um token vazado) consegue tudo o que a sessão consegue. Pedir
a senha transforma essas ações em algo que só o dono da conta faz, e não qualquer
um que alcance o navegador dele.

Trocar o e-mail é a mais sensível das três, porque é ela que redireciona a
recuperação de senha — sem a exigência, um invasor trocaria o endereço e assumiria
a conta em definitivo.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.services.email_service import normalizar_email

User = get_user_model()


class SenhaAtualMixin(serializers.Serializer):
    """Exige e confere a senha atual do usuário autenticado.

    O usuário chega pelo contexto do serializer, e não do corpo da requisição: quem
    está autenticado é fato do servidor, e aceitá-lo do cliente seria permitir agir
    em nome de outra conta.
    """

    senha_atual = serializers.CharField(write_only=True)

    def validate_senha_atual(self, valor: str) -> str:
        """Confere a senha informada contra a do usuário autenticado.

        Args:
            valor (str): Senha em texto plano.

        Returns:
            str: A mesma senha, se conferir.

        Raises:
            serializers.ValidationError: Se a senha não conferir.
        """
        usuario = self.context["request"].user
        if not usuario.check_password(valor):
            raise serializers.ValidationError("Senha atual incorreta.")
        return valor


class PerfilUpdateSerializer(serializers.Serializer):
    """Valida a edição dos dados não sensíveis do perfil.

    Nome de usuário e moeda padrão não redirecionam recuperação de conta nem dão
    acesso a nada, então não pedem a senha atual — exigi-la a cada ajuste de
    preferência treinaria o usuário a digitar a senha sem pensar, o que enfraquece
    a proteção justamente onde ela importa.
    """

    username = serializers.CharField(
        max_length=150, required=False, validators=[UnicodeUsernameValidator()]
    )
    moeda_padrao = serializers.CharField(max_length=10, required=False)

    def validate_username(self, valor: str) -> str:
        """Normaliza e garante que o nome de usuário esteja livre.

        Args:
            valor (str): Nome informado.

        Returns:
            str: Nome sem espaços nas bordas.

        Raises:
            serializers.ValidationError: Se já pertencer a outra conta.
        """
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
        """Normaliza o código da moeda.

        Args:
            valor (str): Código informado.

        Returns:
            str: Código em maiúsculas, sem espaços.

        Raises:
            serializers.ValidationError: Se ficar vazio.
        """
        valor = valor.strip().upper()
        if not valor:
            raise serializers.ValidationError("Informe a moeda padrão.")
        return valor


class TrocaEmailSerializer(SenhaAtualMixin):
    """Valida o pedido de troca de endereço de e-mail."""

    novo_email = serializers.EmailField(max_length=254)

    def validate_novo_email(self, valor: str) -> str:
        """Normaliza o endereço e recusa o que já pertence a outra conta.

        A mensagem de conflito é genérica pelo mesmo motivo do cadastro: confirmar
        que um endereço tem conta no sistema já é informação sensível.

        Args:
            valor (str): Endereço informado.

        Returns:
            str: Endereço normalizado.

        Raises:
            serializers.ValidationError: Se o endereço não puder ser usado.
        """
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
        """Confere a confirmação e aplica os validadores do Django.

        Args:
            dados (dict): Campos já validados individualmente.

        Returns:
            dict: Os mesmos dados, se válidos.

        Raises:
            serializers.ValidationError: Se as senhas divergirem, se a nova for
                igual à atual, ou se for reprovada por algum validador.
        """
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
    """Valida a exclusão definitiva da própria conta.

    Além da senha, exige que o usuário digite o próprio nome. A confirmação
    redundante existe porque a ação é irreversível e apaga anos de histórico
    financeiro: um clique acidental num botão não pode bastar.
    """

    confirmacao = serializers.CharField()

    def validate_confirmacao(self, valor: str) -> str:
        """Confere se o texto digitado corresponde ao nome de usuário.

        Args:
            valor (str): Texto digitado como confirmação.

        Returns:
            str: O mesmo texto, se corresponder.

        Raises:
            serializers.ValidationError: Se não corresponder.
        """
        usuario = self.context["request"].user
        if valor.strip() != usuario.get_username():
            raise serializers.ValidationError(
                "Digite exatamente o seu nome de usuário para confirmar."
            )
        return valor
