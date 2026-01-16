"""
URL configuration for freecash project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from core.views.contas import (
    CadastrarContaPagarView,
    ContaCreateView,
    ContasPagarView,
    MarcarContaPagaView,
    ContaUpdateView,
    ApagarContaView,
)
from core.views.dashboard import DashboardView
from core.views.exportar import ExportarView
from core.views.formas_pagamento import EditarFormaPagamentoView, FormasPagamentoView
from core.views.importar import ImportarView
from core.views.lading import LadingPageView
from core.views.logout_export import LogoutView
from core.views.receitas import ReceitasView, ReceitaUpdateView, ReceitaCreateView
from core.views.transacoes import TransacoesView

urlpatterns = [
    path("admin/", admin.site.urls),
]


urlpatterns += [
    path("", LadingPageView.as_view(), name="landing"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("importar/", ImportarView.as_view(), name="importar"),
    path("exportar/", ExportarView.as_view(), name="exportar"),
    path(
        "formas-de-pagamento/", FormasPagamentoView.as_view(), name="formas_pagamento"
    ),
    path(
        "formas-de-pagamento/<int:pk>/editar/",
        EditarFormaPagamentoView.as_view(),
        name="editar_forma_pagamento",
    ),
    path(
        "contas/cadastrar/",
        CadastrarContaPagarView.as_view(),
        name="cadastrar_conta_pagar",
    ),
    path("transacoes/", TransacoesView.as_view(), name="transacoes"),
    path("receitas/", ReceitasView.as_view(), name="receitas"),
    path("receitas/nova/", ReceitaCreateView.as_view(), name="receita_nova"),
    path(
        "receitas/<int:pk>/editar/", ReceitaUpdateView.as_view(), name="receita_editar"
    ),
    path("investimentos/", include("investimento.urls", namespace="investimento")),
]

urlpatterns += [
    path("contas/", ContasPagarView.as_view(), name="contas_pagar"),
    path("contas/nova/", ContaCreateView.as_view(), name="conta_nova"),
    path(
        "contas/<int:conta_id>/editar/", ContaUpdateView.as_view(), name="conta_editar"
    ),
    path(
        "contas/<int:conta_id>/pagar/",
        MarcarContaPagaView.as_view(),
        name="marcar_conta_paga",
    ),
    path(
        "contas/<int:conta_id>/apagar/", ApagarContaView.as_view(), name="apagar_conta"
    ),
]
