from django.urls import path
from . import views

app_name = "investimento"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    # Classes
    path("classes/", views.classe_listar, name="classe_listar"),
    path("classes/nova/", views.classe_criar, name="classe_criar"),
    path("classes/<int:pk>/editar/", views.classe_editar, name="classe_editar"),
    path("classes/<int:pk>/excluir/", views.classe_excluir, name="classe_excluir"),
    # Ativos
    path("ativos/", views.ativo_listar, name="ativo_listar"),
    path("ativos/novo/", views.ativo_criar, name="ativo_criar"),
    path("ativos/<int:pk>/editar/", views.ativo_editar, name="ativo_editar"),
    path("ativos/<int:pk>/excluir/", views.ativo_excluir, name="ativo_excluir"),
    # Transações
    path("transacoes/", views.transacao_listar, name="transacao_listar"),
    path("transacoes/nova/", views.transacao_criar, name="transacao_criar"),
    path(
        "transacoes/<int:pk>/editar/", views.transacao_editar, name="transacao_editar"
    ),
    path(
        "transacoes/<int:pk>/excluir/",
        views.transacao_excluir,
        name="transacao_excluir",
    ),
]
