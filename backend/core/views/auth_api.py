"""Endpoints de identidade: registro, confirmação de e-mail e redefinição de senha."""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.serializers_auth import (
    EmailVerificacaoSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
)
from core.services.auth_service import revogar_tokens_do_usuario
from core.services.criar_usuario import criar_usuario_com_ecosistema
from core.services.email_service import (
    enviar_reset_senha,
    enviar_verificacao_email,
)
from core.services.tokens import email_verification_token
from core.throttles import AuthScopedRateThrottle, PasswordResetEmailThrottle
from core.views.cookies import clear_refresh_cookie, set_refresh_cookie

logger = logging.getLogger("core")
User = get_user_model()

# Resposta genérica para evitar enumeração de contas cadastradas
RESPOSTA_RESET_GENERICA = {
    "detail": "Se existir uma conta com esse e-mail, enviamos as instruções de "
              "redefinição de senha."
}


def _resolver_usuario(uid: str):
    """Recupera o usuário pelo uid codificado em base64, ou None se inválido."""
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        return User.objects.select_related("config").get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def _dados_do_usuario(user) -> dict:
    """Monta a representação pública do perfil do usuário autenticado."""
    config = getattr(user, "config", None)
    return {
        "username": user.get_username(),
        "email": user.email,
        "email_verificado": bool(config and config.email_verificado),
        "is_staff": user.is_staff,
    }


class RegistrationAPIView(APIView):
    """Cria uma nova conta e agenda o e-mail de confirmação."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request) -> Response:
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        with transaction.atomic():
            usuario = criar_usuario_com_ecosistema(
                dados["username"], dados["password"], dados["email"]
            )
            enviar_verificacao_email(usuario)

        refresh = RefreshToken.for_user(usuario)
        refresh["username"] = usuario.username

        resposta = Response(
            {"access": str(refresh.access_token)}, status=status.HTTP_201_CREATED
        )
        return set_refresh_cookie(resposta, refresh)


class MeAPIView(APIView):
    """Retorna a identidade e o estado atualizado da conta autenticada."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        return Response(_dados_do_usuario(request.user), status=status.HTTP_200_OK)


class EmailVerifyConfirmAPIView(APIView):
    """Confirma o e-mail do usuário a partir do token recebido."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify"

    def post(self, request) -> Response:
        serializer = EmailVerificacaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = _resolver_usuario(serializer.validated_data["uid"])
        if usuario is None:
            return Response(
                {"detail": "Link de confirmação inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = getattr(usuario, "config", None)
        if config is not None and config.email_verificado:
            return Response(
                {
                    "detail": "Este e-mail já está confirmado.",
                    "email_verificado": True,
                },
                status=status.HTTP_200_OK,
            )

        if not email_verification_token.check_token(
            usuario, serializer.validated_data["token"]
        ):
            return Response(
                {
                    "detail": "Link de confirmação inválido ou expirado. "
                              "Solicite um novo a partir do aviso no topo da tela."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        config.email_verificado = True
        config.email_verificado_em = timezone.now()
        config.save(update_fields=["email_verificado", "email_verificado_em",
                                   "atualizada_em"])

        logger.info("E-mail confirmado para o usuário %s.", usuario.pk)
        return Response(
            {"detail": "E-mail confirmado com sucesso.", "email_verificado": True},
            status=status.HTTP_200_OK,
        )


class EmailVerifyResendAPIView(APIView):
    """Reenvia link de confirmação para o e-mail cadastrado da conta autenticada."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify_resend"

    def post(self, request) -> Response:
        usuario = request.user
        config = getattr(usuario, "config", None)

        if config is not None and config.email_verificado:
            return Response(
                {"detail": "Este e-mail já está confirmado.",
                 "email_verificado": True},
                status=status.HTTP_200_OK,
            )

        if not usuario.email:
            return Response(
                {"detail": "Esta conta não tem e-mail cadastrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enviar_verificacao_email(usuario)
        return Response(
            {"detail": "Enviamos um novo link de confirmação para o seu e-mail."},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestAPIView(APIView):
    """Recebe pedido de redefinição de senha com resposta genérica anti-enumeração."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle, PasswordResetEmailThrottle]
    throttle_scope = "senha_reset"

    def post(self, request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        usuario = (
            User.objects.filter(email__iexact=email, is_active=True)
            .order_by("pk")
            .first()
        )

        if usuario is not None:
            enviar_reset_senha(usuario, default_token_generator.make_token(usuario))
        else:
            logger.info("Pedido de redefinição para endereço sem conta ativa.")

        return Response(RESPOSTA_RESET_GENERICA, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmAPIView(APIView):
    """Valida token e efetiva a redefinição de senha, revogando sessões ativas."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        usuario = _resolver_usuario(dados["uid"])
        if usuario is None or not default_token_generator.check_token(
            usuario, dados["token"]
        ):
            return Response(
                {
                    "detail": "Link de redefinição inválido ou expirado. "
                              "Solicite um novo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(dados["nova_senha"], user=usuario)
        except DjangoValidationError as erro:
            return Response(
                {"nova_senha": list(erro.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario.set_password(dados["nova_senha"])
        usuario.save(update_fields=["password"])

        config = getattr(usuario, "config", None)
        if config is not None and not config.email_verificado:
            config.email_verificado = True
            config.email_verificado_em = timezone.now()
            config.save(
                update_fields=["email_verificado", "email_verificado_em",
                               "atualizada_em"]
            )

        revogar_tokens_do_usuario(usuario)
        logger.info("Senha redefinida para o usuário %s.", usuario.pk)

        resposta = Response(
            {"detail": "Senha alterada com sucesso. Faça login com a nova senha."},
            status=status.HTTP_200_OK,
        )
        return clear_refresh_cookie(resposta)

