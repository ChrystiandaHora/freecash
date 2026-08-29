"""Endpoints do painel administrativo da plataforma.

**Limite de privacidade, não negociável:** estes endpoints expõem apenas metadados
de conta — nome de usuário, e-mail, datas, estado de verificação, estado de
atividade e contagens. Nunca transações, saldos, ativos ou qualquer valor
financeiro. Administrar a plataforma não exige ver as finanças de ninguém, e o
produto guarda informação financeira pessoal de terceiros.

Se um campo financeiro aparecer aqui no futuro, o teste
`test_api_admin.py::test_resposta_nao_expoe_dado_financeiro` falha — ele existe
justamente para que essa fronteira não seja atravessada por descuido.

A suspensão usa `is_active=False` do próprio `auth.User`, e não uma flag nova. A
vantagem é que o enforcement vem de graça e em dois níveis: o backend de
autenticação recusa o login, e o `JWTAuthentication` do SimpleJWT verifica
`is_active` a cada requisição, de modo que o access token de quem foi suspenso para
de funcionar na chamada seguinte, sem esperar os 15 minutos de validade.
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import LogAcaoAdmin
from core.pagination import PadraoPageNumberPagination
from core.permissions import IsAdminPlataforma
from core.serializers_admin import (
    LogAcaoAdminSerializer,
    UsuarioAdminDetalheSerializer,
    UsuarioAdminSerializer,
)
from core.services.admin_metrics_service import coletar_metricas
from core.services.auth_service import revogar_tokens_do_usuario

logger = logging.getLogger("core")
User = get_user_model()


class AdminPaginacao(PadraoPageNumberPagination):
    """Paginação do painel: sempre ativa, com página menor que a do restante da API.

    A paginação padrão do projeto é opt-in por requisição, para não alterar o
    formato de resposta das telas existentes. Aqui não há histórico a preservar: a
    lista de contas nasce paginada, e o envelope é sempre devolvido.
    """

    page_size = 25

    def paginate_queryset(self, queryset, request, view=None):
        """Pagina sempre, independentemente do parâmetro `page`.

        Args:
            queryset (QuerySet): Conjunto de resultados a paginar.
            request (Request): Requisição em processamento.
            view (APIView | None): View que originou a listagem.

        Returns:
            list: A página solicitada.
        """
        # Chama diretamente a implementação do DRF, saltando o atalho de opt-in.
        return super(PadraoPageNumberPagination, self).paginate_queryset(
            queryset, request, view
        )


def _queryset_usuarios():
    """Monta a consulta base de contas com os agregados exibidos no painel.

    Returns:
        QuerySet: Usuários com `config` pré-carregado e as contagens de volume de
            dados anotadas — `annotate` em vez de laço em Python, para que a
            listagem não degrade conforme a base cresce.
    """
    return (
        User.objects.select_related("config")
        .annotate(
            total_lancamentos=Count("contas", distinct=True),
            total_ativos=Count("ativos", distinct=True),
        )
        .order_by("-date_joined")
    )


class AdminUsuariosListAPIView(ListAPIView):
    """Lista as contas da plataforma, com busca e filtros."""

    permission_classes = [IsAdminPlataforma]
    serializer_class = UsuarioAdminSerializer
    pagination_class = AdminPaginacao

    def get_queryset(self):
        """Aplica busca textual e filtros de estado.

        Returns:
            QuerySet: Contas correspondentes aos parâmetros da requisição.
        """
        queryset = _queryset_usuarios()
        params = self.request.query_params

        busca = (params.get("busca") or "").strip()
        if busca:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(username__icontains=busca) | Q(email__icontains=busca)
            )

        ativo = params.get("ativo")
        if ativo in {"true", "false"}:
            queryset = queryset.filter(is_active=(ativo == "true"))

        verificado = params.get("verificado")
        if verificado in {"true", "false"}:
            queryset = queryset.filter(
                config__email_verificado=(verificado == "true")
            )

        return queryset


class AdminUsuarioDetalheAPIView(RetrieveAPIView):
    """Exibe os metadados de uma conta específica."""

    permission_classes = [IsAdminPlataforma]
    serializer_class = UsuarioAdminDetalheSerializer

    def get_queryset(self):
        """Reaproveita a consulta base da listagem.

        Returns:
            QuerySet: Contas com os mesmos agregados da listagem.
        """
        return _queryset_usuarios()


class _AlterarEstadoContaBase(APIView):
    """Base das ações que ligam e desligam o acesso de uma conta.

    Atributos:
        ativar (bool): Estado de `is_active` que a ação aplica.
        acao (str): Valor registrado em `LogAcaoAdmin.acao`.
    """

    permission_classes = [IsAdminPlataforma]
    ativar = True
    acao = LogAcaoAdmin.ACAO_REATIVAR

    def post(self, request, pk) -> Response:
        """Aplica o novo estado à conta e registra a ação.

        Args:
            request (Request): Requisição do administrador.
            pk (int): Chave primária da conta afetada.

        Returns:
            Response: 200 com o estado resultante, 404 se a conta não existe, ou
                400 se o administrador tentar alterar a própria conta.
        """
        alvo = User.objects.select_related("config").filter(pk=pk).first()
        if alvo is None:
            return Response(
                {"detail": "Conta não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Suspender a si mesmo tiraria o próprio acesso ao painel, possivelmente
        # deixando a plataforma sem nenhum administrador operante.
        if alvo.pk == request.user.pk:
            return Response(
                {"detail": "Não é possível alterar o estado da sua própria conta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if alvo.is_active == self.ativar:
            return Response(
                {
                    "detail": "A conta já está neste estado.",
                    "is_active": alvo.is_active,
                },
                status=status.HTTP_200_OK,
            )

        with transaction.atomic():
            alvo.is_active = self.ativar
            alvo.save(update_fields=["is_active"])

            LogAcaoAdmin.objects.create(
                ator=request.user,
                ator_username=request.user.get_username(),
                alvo=alvo,
                alvo_username=alvo.get_username(),
                acao=self.acao,
                detalhe=(request.data.get("detalhe") or "").strip()[:2000],
            )

            # Ao suspender, encerra também as sessões já abertas. Sem isto, o
            # refresh token continuaria renovando o acesso por até sete dias.
            if not self.ativar:
                revogar_tokens_do_usuario(alvo)

        logger.info(
            "Conta %s %s pelo administrador %s.",
            alvo.pk,
            "reativada" if self.ativar else "suspensa",
            request.user.pk,
        )

        return Response(
            {
                "detail": (
                    "Conta reativada." if self.ativar else "Conta suspensa."
                ),
                "is_active": alvo.is_active,
            },
            status=status.HTTP_200_OK,
        )


class AdminSuspenderUsuarioAPIView(_AlterarEstadoContaBase):
    """Suspende o acesso de uma conta e encerra as sessões abertas dela."""

    ativar = False
    acao = LogAcaoAdmin.ACAO_SUSPENDER


class AdminReativarUsuarioAPIView(_AlterarEstadoContaBase):
    """Devolve o acesso a uma conta suspensa."""

    ativar = True
    acao = LogAcaoAdmin.ACAO_REATIVAR


class AdminMetricasAPIView(APIView):
    """Devolve os indicadores de uso da plataforma."""

    permission_classes = [IsAdminPlataforma]

    def get(self, request) -> Response:
        """Coleta as métricas agregadas.

        Args:
            request (Request): Requisição do administrador. Aceita `dias` para
                ajustar a janela da série de cadastros.

        Returns:
            Response: 200 com os indicadores.
        """
        try:
            dias = int(request.query_params.get("dias", 30))
        except (TypeError, ValueError):
            dias = 30

        # Teto para que o parâmetro não sirva de vetor para uma consulta enorme.
        dias = max(7, min(dias, 180))

        return Response(coletar_metricas(dias_serie=dias), status=status.HTTP_200_OK)


class AdminLogsAPIView(ListAPIView):
    """Lista o histórico de ações administrativas."""

    permission_classes = [IsAdminPlataforma]
    serializer_class = LogAcaoAdminSerializer
    pagination_class = AdminPaginacao
    queryset = LogAcaoAdmin.objects.all()
