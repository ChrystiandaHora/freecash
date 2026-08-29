"""Endpoints das operações que o usuário faz sobre a própria conta.

Perfil, troca de e-mail, troca de senha e exclusão. Ficam separados de
`auth_api.py` — que trata de *entrar* no sistema — porque aqui o usuário já está
autenticado e o assunto é administrar a própria identidade.

Três princípios atravessam o arquivo:

**A senha atual é exigida no que redireciona ou destrói acesso.** Quem alcança uma
sessão aberta consegue tudo o que a sessão consegue; pedir a senha transforma essas
ações em algo que só o dono faz. Editar nome ou moeda não pede, de propósito:
exigir a senha a cada ajuste de preferência treinaria o usuário a digitá-la sem
pensar, enfraquecendo a proteção onde ela importa.

**A troca de e-mail não vale antes de confirmada.** O novo endereço fica em
`email_pendente` e só substitui `User.email` quando o link enviado a ele é aberto.
Um erro de digitação, assim, não deixa a conta sem endereço válido para
recuperação; e quem tomasse uma sessão não conseguiria trancar o dono para fora.

**Trocar senha encerra as outras sessões.** Se a senha foi trocada porque vazou,
manter as sessões abertas preservaria o acesso do invasor exatamente no momento em
que a vítima acredita ter resolvido o problema.
"""

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
    """Monta a representação da conta para as telas de perfil.

    Args:
        user (User): Usuário autenticado.

    Returns:
        dict: Identidade, estado de verificação e preferências.
    """
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
    """Lê e edita os dados não sensíveis da conta autenticada."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve os dados da conta.

        Args:
            request (Request): Requisição autenticada.

        Returns:
            Response: 200 com os dados da conta.
        """
        return Response(_dados_da_conta(request.user), status=status.HTTP_200_OK)

    def patch(self, request) -> Response:
        """Atualiza nome de usuário e preferências.

        Args:
            request (Request): Requisição com os campos a alterar.

        Returns:
            Response: 200 com os dados atualizados, ou 400 com os erros por campo.
        """
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
    """Inicia a troca de endereço de e-mail da conta."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify_resend"

    def post(self, request) -> Response:
        """Registra o novo endereço como pendente e envia o link de confirmação.

        Args:
            request (Request): Requisição com `senha_atual` e `novo_email`.

        Returns:
            Response: 202 informando que a confirmação foi enviada, ou 400 com os
                erros por campo.
        """
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
            # Recarrega para que o gerador de token assine o endereço recém-gravado.
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
    """Descarta uma troca de e-mail ainda não confirmada."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        """Limpa o endereço pendente, invalidando o link já enviado.

        Args:
            request (Request): Requisição autenticada.

        Returns:
            Response: 200 com os dados da conta.
        """
        config = getattr(request.user, "config", None)
        if config is not None and config.email_pendente:
            config.email_pendente = ""
            config.save(update_fields=["email_pendente", "atualizada_em"])

        request.user.refresh_from_db()
        return Response(_dados_da_conta(request.user), status=status.HTTP_200_OK)


class TrocaEmailConfirmarAPIView(APIView):
    """Efetiva a troca de e-mail a partir do link enviado ao novo endereço.

    Aberta a anônimos de propósito: o link chega num e-mail e costuma ser aberto em
    outro navegador, sem sessão. A autorização vem do próprio token, que só pôde ser
    gerado por quem já provou a senha atual.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "email_verify"

    def post(self, request) -> Response:
        """Valida o token e promove o endereço pendente a endereço da conta.

        Args:
            request (Request): Requisição com `uid` e `token`.

        Returns:
            Response: 200 quando a troca é concluída, ou 400 se o link for
                inválido, expirado ou já utilizado.
        """
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
            # Quem abriu o link provou ter acesso à caixa de entrada do endereço.
            config.email_verificado = True
            config.email_verificado_em = timezone.now()
            config.save(update_fields=[
                "email_pendente", "email_verificado", "email_verificado_em",
                "atualizada_em",
            ])

            # Vai para o endereço ANTIGO: é a rede de segurança de quem não pediu
            # a troca, e o único canal que ainda o alcança.
            avisar_troca_de_email(usuario, email_anterior)

        logger.info("E-mail alterado para o usuário %s.", usuario.pk)
        return Response(
            {"detail": "E-mail alterado com sucesso.", "email": usuario.email},
            status=status.HTTP_200_OK,
        )


class TrocaSenhaAPIView(APIView):
    """Troca a senha de um usuário já autenticado."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        """Valida a senha atual, aplica a nova e renova a sessão em curso.

        As demais sessões são revogadas. A atual é preservada por um cookie novo:
        deslogar quem acabou de trocar a própria senha, no exato momento em que
        demonstrou ser o dono, seria hostil sem ganho de segurança.

        Args:
            request (Request): Requisição com `senha_atual`, `nova_senha` e `confirmar`.

        Returns:
            Response: 200 com um token de acesso novo, ou 400 com os erros por campo.
        """
        serializer = TrocaSenhaSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        usuario = request.user
        usuario.set_password(serializer.validated_data["nova_senha"])
        usuario.save(update_fields=["password"])

        # Revoga tudo o que existia antes, inclusive a sessão atual...
        revogar_tokens_do_usuario(usuario)
        # ...e devolve uma sessão nova só para quem fez a troca.
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
    """Apaga definitivamente a conta do usuário e todos os seus dados."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        """Remove a conta após dupla confirmação.

        Exige a senha atual e o nome de usuário digitado por extenso. A ação é
        irreversível e leva junto todo o histórico financeiro, então um clique
        acidental não pode bastar.

        Args:
            request (Request): Requisição com `senha_atual` e `confirmacao`.

        Returns:
            Response: 200 com o cookie de sessão removido, ou 400 com os erros.
        """
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
    """Conta os refresh tokens vivos de um usuário.

    Uma sessão existe enquanto o seu refresh token não expirou e não foi revogado.
    Os dados vêm do próprio app de blacklist do SimpleJWT, sem modelo novo.

    **A contagem superestima.** Com `ROTATE_REFRESH_TOKENS`, cada renovação emite um
    token novo e revoga o anterior — então uma sessão em uso contribui com exatamente
    um token. Mas uma sessão abandonada sem logout deixa o seu último token pendente
    até expirar, e continua sendo contada por até sete dias. Por isso a interface
    fala em "dispositivos conectados nos últimos 7 dias", e não afirma uma precisão
    que o dado não tem.

    Args:
        usuario (User): Dono das sessões.

    Returns:
        int: Quantidade de refresh tokens ainda válidos.
    """
    return (
        OutstandingToken.objects.filter(
            user=usuario,
            expires_at__gt=timezone.now(),
            blacklistedtoken__isnull=True,
        ).count()
    )


class SessoesAPIView(APIView):
    """Informa quantas sessões da conta estão ativas."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve a contagem de sessões ativas.

        Args:
            request (Request): Requisição autenticada.

        Returns:
            Response: 200 com a contagem e a janela a que ela se refere.
        """
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
    """Encerra as demais sessões da conta, mantendo a de quem pediu."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "senha_reset_confirm"

    def post(self, request) -> Response:
        """Revoga todas as sessões e devolve uma nova ao chamador.

        **Por que revogar todas, inclusive a atual:** o cookie do refresh token é
        gravado com `path=/api/token/`, então ele não é enviado a esta rota — não há
        como identificar qual dos tokens pendentes pertence a quem está pedindo, e
        portanto não há como poupá-lo seletivamente.

        Alargar o path do cookie resolveria a identificação, mas ao custo de expor o
        refresh token a todas as rotas de dados. Revogar tudo e emitir uma sessão
        nova para o chamador chega ao mesmo resultado observável — só a sessão atual
        sobrevive — sem ampliar essa superfície. É o mesmo mecanismo que a troca de
        senha já usa.

        Args:
            request (Request): Requisição autenticada.

        Returns:
            Response: 200 com um token de acesso novo e o cookie renovado.
        """
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
