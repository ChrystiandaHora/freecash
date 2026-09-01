"""Endpoints de gestão da própria conta (perfil, e-mail, senha, sessões e exclusão)."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from core.serializers_conta import (
    ExclusaoContaSerializer,
    PerfilUpdateSerializer,
    TrocaEmailSerializer,
    TrocaSenhaSerializer,
)
from core.services.auth_service import revogar_tokens_do_usuario
from core.services.email_service import (
    avisar_troca_de_email,
    enviar_confirmacao_troca_email,
)
from core.services.tokens import email_change_token
from core.throttles import AuthScopedRateThrottle
from core.views.cookies import clear_refresh_cookie, set_refresh_cookie

logger = logging.getLogger("core")
User = get_user_model()


def _dados_da_conta(user) -> dict:
    """Monta a representação da conta para o perfil."""
    config = getattr(user, "config", None)
    return {
        "username": user.get_username(),
        "email": user.email,
        "email_verificado": bool(config and config.email_verificado),
        "email_pendente": getattr(config, "email_pendente", "") if config else "",
        "moeda_padrao": getattr(config, "moeda_padrao", "BRL") if config else "BRL",
        "is_staff": user.is_staff,
        "data_cadastro": user.date_joined.isoformat(),
    }


class PerfilAPIView(APIView):
    """Lê e atualiza dados não sensíveis da conta autenticada."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        return Response(_dados_da_conta(request.user), status=status.HTTP_200_OK)

    def patch(self, request) -> Response:
        serializer = PerfilUpdateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        usuario = request.user
        config = getattr(usuario, "config", None)

        with transaction.atomic():
            if "username" in dados:
                usuario.username = dados["username"]
                usuario.save(update_fields=["username"])

            if "moeda_padrao" in dados and config is not None:
                config.moeda_padrao = dados["moeda_padrao"]
                config.save(update_fields=["moeda_padrao", "atualizada_em"])

        usuario.refresh_from_db()
        return Response(_dados_da_conta(usuario), status=status.HTTP_200_OK)


class TrocaEmailSolicitarAPIView(APIView):
    """Inicia a troca de e-mail enviando link de confirmação para o novo endereço."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify_resend"

    def post(self, request) -> Response:
        serializer = TrocaEmailSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        usuario = request.user
        config = getattr(usuario, "config", None)
        if config is None:
            return Response(
                {"detail": "Configuração da conta não encontrada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            config.email_pendente = serializer.validated_data["novo_email"]
            config.save(update_fields=["email_pendente", "atualizada_em"])
            usuario.refresh_from_db()
            enviar_confirmacao_troca_email(usuario)

        logger.info("Troca de e-mail solicitada pelo usuário %s.", usuario.pk)
        return Response(
            {
                "detail": "Enviamos um link de confirmação para o novo endereço. "
                          "Seu e-mail atual continua valendo até você confirmar.",
                "email_pendente": config.email_pendente,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TrocaEmailCancelarAPIView(APIView):
    """Descarta a solicitação de troca de e-mail pendente."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        config = getattr(request.user, "config", None)
        if config is not None and config.email_pendente:
            config.email_pendente = ""
            config.save(update_fields=["email_pendente", "atualizada_em"])

        request.user.refresh_from_db()
        return Response(_dados_da_conta(request.user), status=status.HTTP_200_OK)


class TrocaEmailConfirmarAPIView(APIView):
    """Efetiva a troca de e-mail a partir do link de confirmação."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify"

    def post(self, request) -> Response:
        uid = request.data.get("uid")
        token = request.data.get("token")
        if not uid or not token:
            return Response(
                {"detail": "Link de confirmação inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            pk = force_str(urlsafe_base64_decode(uid))
            usuario = User.objects.select_related("config").get(pk=pk)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": "Link de confirmação inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = getattr(usuario, "config", None)
        if config is None or not config.email_pendente:
            return Response(
                {"detail": "Não há troca de e-mail pendente para esta conta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email_change_token.check_token(usuario, token):
            return Response(
                {"detail": "Link de confirmação inválido ou expirado. "
                           "Solicite a troca novamente."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_anterior = usuario.email
        novo_email = config.email_pendente

        with transaction.atomic():
            usuario.email = novo_email
            usuario.save(update_fields=["email"])

            config.email_pendente = ""
            config.email_verificado = True
            config.email_verificado_em = timezone.now()
            config.save(update_fields=[
                "email_pendente", "email_verificado", "email_verificado_em",
                "atualizada_em",
            ])

            avisar_troca_de_email(usuario, email_anterior)

        logger.info("E-mail alterado para o usuário %s.", usuario.pk)
        return Response(
            {"detail": "E-mail alterado com sucesso.", "email": usuario.email},
            status=status.HTTP_200_OK,
        )


class TrocaSenhaAPIView(APIView):
    """Atualiza a senha do usuário, revogando outras sessões ativas."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        serializer = TrocaSenhaSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        usuario = request.user
        usuario.set_password(serializer.validated_data["nova_senha"])
        usuario.save(update_fields=["password"])

        revogar_tokens_do_usuario(usuario)
        refresh = RefreshToken.for_user(usuario)
        refresh["username"] = usuario.username

        logger.info("Senha alterada pelo próprio usuário %s.", usuario.pk)

        resposta = Response(
            {
                "detail": "Senha alterada com sucesso. As outras sessões foram encerradas.",
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )
        return set_refresh_cookie(resposta, refresh)


class ExcluirContaAPIView(APIView):
    """Exclui definitivamente a conta e todos os dados financeiros vinculados."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        serializer = ExclusaoContaSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        usuario = request.user
        identificacao = usuario.pk

        with transaction.atomic():
            revogar_tokens_do_usuario(usuario)
            usuario.delete()

        logger.info("Conta %s excluída a pedido do próprio usuário.", identificacao)

        resposta = Response(
            {"detail": "Sua conta e todos os seus dados foram excluídos."},
            status=status.HTTP_200_OK,
        )
        return clear_refresh_cookie(resposta)


def _contar_sessoes_ativas(usuario) -> int:
    """Retorna o total de refresh tokens válidos do usuário."""
    return (
        OutstandingToken.objects.filter(
            user=usuario,
            expires_at__gt=timezone.now(),
            blacklistedtoken__isnull=True,
        ).count()
    )


class SessoesAPIView(APIView):
    """Retorna a contagem de sessões ativas do usuário."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        return Response(
            {
                "ativas": _contar_sessoes_ativas(request.user),
                "janela_dias": int(
                    settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].days
                ),
            },
            status=status.HTTP_200_OK,
        )


class EncerrarOutrasSessoesAPIView(APIView):
    """Revoga todas as sessões anteriores e renova a sessão atual do chamador."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        usuario = request.user
        encerradas = revogar_tokens_do_usuario(usuario)

        refresh = RefreshToken.for_user(usuario)
        refresh["username"] = usuario.username

        logger.info(
            "Usuário %s encerrou as outras sessões (%d revogadas).",
            usuario.pk, encerradas,
        )

        resposta = Response(
            {
                "detail": "As outras sessões foram encerradas.",
                "access": str(refresh.access_token),
                "ativas": _contar_sessoes_ativas(usuario),
            },
            status=status.HTTP_200_OK,
        )
        return set_refresh_cookie(resposta, refresh)

