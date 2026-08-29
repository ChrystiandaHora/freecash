"""Endpoints de identidade: registro, confirmação de e-mail e redefinição de senha.

Estas views ficam num módulo próprio porque `core/views/api.py` já passa de 1900
linhas e concentra o domínio financeiro. Identidade é outro assunto, com outras
regras de segurança, e merece ser lida em isolamento.

Três princípios atravessam o arquivo:

**Não revelar quem tem conta.** O pedido de redefinição de senha responde
exatamente a mesma coisa exista ou não a conta. Num sistema financeiro, confirmar
que um endereço tem conta já é informação sensível.

**Idempotência onde o usuário pode repetir a ação.** Confirmar um e-mail já
confirmado responde sucesso, não erro: clicar duas vezes no link do e-mail é
comportamento normal e não deveria produzir uma tela de falha.

**Nada de estado em claim de JWT.** Com `ROTATE_REFRESH_TOKENS`, o SimpleJWT
reaproveita o payload do refresh na rotação, trocando apenas `jti` e `exp`. Uma
claim como `email_verificado` ficaria desatualizada por até sete dias. Estado
mutável é servido por `GET /api/auth/me/`, que sempre lê do banco.
"""

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

# Resposta única do pedido de redefinição de senha. Vale para endereço cadastrado,
# não cadastrado ou de conta inativa — é o que impede a enumeração de contas.
RESPOSTA_RESET_GENERICA = {
    "detail": "Se existir uma conta com esse e-mail, enviamos as instruções de "
              "redefinição de senha."
}


def _resolver_usuario(uid: str):
    """Recupera o usuário a partir do identificador codificado no link.

    Args:
        uid (str): Chave primária do usuário em base64 segura para URL.

    Returns:
        User | None: O usuário correspondente, ou None se o identificador for
            inválido, malformado ou não existir. Nunca levanta exceção: um `uid`
            corrompido é entrada do usuário, e deve resultar em 400, não em 500.
    """
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        return User.objects.select_related("config").get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def _dados_do_usuario(user) -> dict:
    """Monta a representação pública do usuário autenticado.

    Args:
        user (User): Usuário autenticado.

    Returns:
        dict: Identidade e estado de verificação, além do papel administrativo.
    """
    config = getattr(user, "config", None)
    return {
        "username": user.get_username(),
        "email": user.email,
        "email_verificado": bool(config and config.email_verificado),
        "is_staff": user.is_staff,
    }


class RegistrationAPIView(APIView):
    """Cria uma nova conta e inicia a confirmação do endereço de e-mail.

    A conta é criada com o ecossistema financeiro básico (configurações e categorias
    padrão) numa única transação, e o usuário já recebe os tokens de sessão: exigir
    a confirmação do e-mail antes do primeiro acesso criaria contas órfãs, com todo
    o ecossistema provisionado e sem ninguém capaz de entrar para pedir o reenvio.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request) -> Response:
        """Registra o usuário e devolve os tokens iniciais de sessão.

        Args:
            request (Request): Requisição com username, email, password e confirm.

        Returns:
            Response: 201 com o token de acesso e o cookie do refresh token, ou 400
                com os erros por campo.
        """
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        with transaction.atomic():
            usuario = criar_usuario_com_ecosistema(
                dados["username"], dados["password"], dados["email"]
            )
            # Agendado para depois do commit: se a transação for desfeita, o e-mail
            # não sai, e o usuário não recebe confirmação de uma conta inexistente.
            enviar_verificacao_email(usuario)

        refresh = RefreshToken.for_user(usuario)
        refresh["username"] = usuario.username

        resposta = Response(
            {"access": str(refresh.access_token)}, status=status.HTTP_201_CREATED
        )
        return set_refresh_cookie(resposta, refresh)


class MeAPIView(APIView):
    """Informa a identidade e o estado da conta autenticada.

    Existe porque o frontend não pode confiar no conteúdo do JWT para estado
    mutável: a rotação de refresh token preserva o payload original, então um valor
    embutido no token ficaria obsoleto por até sete dias. Um administrador
    rebaixado, por exemplo, continuaria com o papel antigo por uma semana.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve os dados da conta autenticada, lidos do banco.

        Args:
            request (Request): Requisição autenticada.

        Returns:
            Response: 200 com identidade, e-mail e estado de verificação.
        """
        return Response(_dados_do_usuario(request.user), status=status.HTTP_200_OK)


class EmailVerifyConfirmAPIView(APIView):
    """Confirma a posse do endereço de e-mail a partir do link recebido.

    É `POST`, e o link do e-mail aponta para o SPA em vez de para esta rota, por um
    motivo prático: clientes de e-mail e filtros corporativos pré-carregam as URLs
    das mensagens. Se o link fosse um `GET` neste endpoint, o token seria consumido
    antes de o usuário clicar.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify"

    def post(self, request) -> Response:
        """Valida o token e marca o e-mail como verificado.

        Args:
            request (Request): Requisição com `uid` e `token`.

        Returns:
            Response: 200 quando o e-mail está confirmado — inclusive se já
                estivesse, para que um segundo clique no link não pareça erro — ou
                400 se o token for inválido, expirado ou já utilizado.
        """
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
    """Reenvia o link de confirmação para a conta autenticada.

    Exige autenticação de propósito. Um endpoint aberto que aceitasse um e-mail
    qualquer serviria para descobrir quem tem conta no sistema e para usar o
    servidor como disparador de mensagens contra terceiros.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify_resend"

    def post(self, request) -> Response:
        """Dispara um novo e-mail de confirmação, se ainda for necessário.

        Args:
            request (Request): Requisição autenticada.

        Returns:
            Response: 200 sempre que a situação já é a desejada ou o envio foi
                agendado; 400 se a conta não tem endereço cadastrado.
        """
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
    """Recebe o pedido de redefinição de senha e envia o link, se couber."""

    permission_classes = [permissions.AllowAny]
    # Dois limites somados: por IP, para conter varredura; e por endereço de destino,
    # para que o sistema não seja usado como disparador de mensagens contra alguém.
    throttle_classes = [AuthScopedRateThrottle, PasswordResetEmailThrottle]
    throttle_scope = "senha_reset"

    def post(self, request) -> Response:
        """Envia o link de redefinição sem revelar se a conta existe.

        Args:
            request (Request): Requisição com o campo `email`.

        Returns:
            Response: 202 com a mesma mensagem em todos os casos.
        """
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
            # Registrado apenas no log: a resposta ao cliente não muda.
            logger.info("Pedido de redefinição para endereço sem conta ativa.")

        return Response(RESPOSTA_RESET_GENERICA, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmAPIView(APIView):
    """Efetiva a troca de senha a partir do link recebido por e-mail."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        """Valida o token, troca a senha e encerra as sessões existentes.

        O `default_token_generator` do Django inclui o hash da senha e o
        `last_login` no valor assinado, então a troca de senha invalida o próprio
        token — uso único, sem tabela de controle.

        Args:
            request (Request): Requisição com `uid`, `token`, `nova_senha` e `confirmar`.

        Returns:
            Response: 200 com o cookie de sessão removido, ou 400 se o token for
                inválido ou a senha reprovada pelos validadores.
        """
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

        # Quem chegou até aqui provou ter acesso à caixa de entrada do endereço.
        config = getattr(usuario, "config", None)
        if config is not None and not config.email_verificado:
            config.email_verificado = True
            config.email_verificado_em = timezone.now()
            config.save(
                update_fields=["email_verificado", "email_verificado_em",
                               "atualizada_em"]
            )

        # Se a senha foi trocada porque a anterior vazou, as sessões abertas com ela
        # precisam morrer — inclusive as do atacante.
        revogar_tokens_do_usuario(usuario)

        logger.info("Senha redefinida para o usuário %s.", usuario.pk)

        resposta = Response(
            {"detail": "Senha alterada com sucesso. Faça login com a nova senha."},
            status=status.HTTP_200_OK,
        )
        return clear_refresh_cookie(resposta)
