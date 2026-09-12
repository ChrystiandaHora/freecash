"""Endpoints do painel administrativo da plataforma (contas, métricas e auditoria)."""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
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
    """Paginação padrão do painel administrativo (25 itens por página)."""

    page_size = 25

    def paginate_queryset(self, queryset, request, view=None):
        return super(PadraoPageNumberPagination, self).paginate_queryset(
            queryset, request, view
        )


def _queryset_usuarios():
    """Retorna a query base de usuários com contagens agregadas."""
    return (
        User.objects.select_related("config")
        .annotate(
            total_lancamentos=Count("contas", distinct=True),
            total_ativos=Count("ativos", distinct=True),
        )
        .order_by("-date_joined")
    )


class AdminUsuariosListAPIView(ListAPIView):
    """Lista as contas da plataforma com suporte a filtros e busca textual."""

    permission_classes = [IsAdminPlataforma]
    serializer_class = UsuarioAdminSerializer
    pagination_class = AdminPaginacao

    def get_queryset(self):
        queryset = _queryset_usuarios()
        params = self.request.query_params

        busca = (params.get("busca") or "").strip()
        if busca:
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
        return _queryset_usuarios()


class _AlterarEstadoContaBase(APIView):
    """Base para suspensão e reativação de contas."""

    permission_classes = [IsAdminPlataforma]
    ativar = True
    acao = LogAcaoAdmin.ACAO_REATIVAR

    def post(self, request, pk: int) -> Response:
        alvo = User.objects.select_related("config").filter(pk=pk).first()
        if alvo is None:
            return Response(
                {"detail": "Conta não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

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
    """Suspende a conta e revoga suas sessões ativas."""

    ativar = False
    acao = LogAcaoAdmin.ACAO_SUSPENDER


class AdminReativarUsuarioAPIView(_AlterarEstadoContaBase):
    """Reativa uma conta suspensa."""

    ativar = True
    acao = LogAcaoAdmin.ACAO_REATIVAR


class AdminMetricasAPIView(APIView):
    """Retorna os indicadores agregados de uso da plataforma."""

    permission_classes = [IsAdminPlataforma]

    def get(self, request) -> Response:
        try:
            dias = int(request.query_params.get("dias", 30))
        except (TypeError, ValueError):
            dias = 30

        dias = max(7, min(dias, 180))
        return Response(coletar_metricas(dias_serie=dias), status=status.HTTP_200_OK)


class AdminLogsAPIView(ListAPIView):
    """Lista o histórico de auditoria de ações administrativas."""

    permission_classes = [IsAdminPlataforma]
    serializer_class = LogAcaoAdminSerializer
    pagination_class = AdminPaginacao
    queryset = LogAcaoAdmin.objects.all()

