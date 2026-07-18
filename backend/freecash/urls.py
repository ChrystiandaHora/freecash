"""Módulo de Mapeamento de Rotas da API REST do FreeCash.

Este arquivo configura centralizadamente as URLs e pontos de entrada expostos do
backend Django. Ele registra os roteadores (DefaultRouter) do Django REST Framework
e define os endpoints de autenticação via cookies (tokens JWT), dashboard consolidado,
relatórios financeiros e ferramentas administrativas de conciliação bancária de OFX.

Barramento de APIs:
    /api/token/ : Endpoints de controle de sessão JWT (Obtain, Refresh, Clear).
    /api/dashboard/ : Agregados estatísticos mensais de finanças.
    /api/financeiro/ : Lançamentos de despesas, receitas, transações e cartões de crédito.
    /api/investimentos/ : Carteira ativa e simulador de alocação/balanceamento.
    /api/ferramentas/ : Importação de OFX, conciliação e exportação de relatórios.
"""


from django.contrib import admin
from django.urls import path, include
urlpatterns = [
    path("admin/", admin.site.urls),
]

# REST API Routing Configuration
from rest_framework.routers import DefaultRouter
from core.views.api import (
    CategoriaViewSet, CartaoCreditoViewSet, ContaViewSet, DashboardAPIView,
    CookieTokenObtainPairView, CookieTokenRefreshView, CookieTokenClearView,
    CartaoCreditoAPIViewSet, ContasPagarViewSet, ReceitasViewSet,
    TransacoesViewSet, RelatoriosDREAPIView, RegistrationAPIView,
    ExecutiveBIDashboardAPIView, ComprasCartaoViewSet
)
from investimento.views_api import (
    ClasseAtivoViewSet, CategoriaAtivoViewSet, SubcategoriaAtivoViewSet, 
    AtivoViewSet, TransacaoInvestimentoViewSet, DashboardInvestimentoAPIView
)
from core.views.ferramentas_api import (
    FerramentasImportarAPIView,
    FerramentasImportarExtratoAPIView,
    FerramentasConciliacaoListAPIView,
    FerramentasConciliacaoProcessarAPIView,
    FerramentasExportarAPIView,
    ContasBancariasViewSet,
)

# API Routers setup
router = DefaultRouter()
router.register(r'categorias', CategoriaViewSet, basename='api-categoria')
router.register(r'cartoes', CartaoCreditoViewSet, basename='api-cartao')
router.register(r'contas', ContaViewSet, basename='api-conta')

# React Frontend Integrated Routers
router.register(r'financeiro/cartoes', CartaoCreditoAPIViewSet, basename='api-financeiro-cartoes')
router.register(r'financeiro/contas-pagar', ContasPagarViewSet, basename='api-financeiro-contas-pagar')
router.register(r'financeiro/receitas', ReceitasViewSet, basename='api-financeiro-receitas')
router.register(r'financeiro/transacoes', TransacoesViewSet, basename='api-financeiro-transacoes')
router.register(r'financeiro/compras-cartao', ComprasCartaoViewSet, basename='api-financeiro-compras-cartao')

router.register(r'investimentos/classes', ClasseAtivoViewSet, basename='api-classe')
router.register(r'investimentos/categorias', CategoriaAtivoViewSet, basename='api-categoria-ativo')
router.register(r'investimentos/subcategorias', SubcategoriaAtivoViewSet, basename='api-subcategoria')
router.register(r'investimentos/ativos', AtivoViewSet, basename='api-ativo')
router.register(r'investimentos/transacoes', TransacaoInvestimentoViewSet, basename='api-transacao-investimento')
router.register(r'configuracoes/contas-bancarias', ContasBancariasViewSet, basename='api-contas-bancarias')

# REST API & Token paths
urlpatterns += [
    path('api/', include(router.urls)),
    path('api/register/', RegistrationAPIView.as_view(), name='api-register'),
    path('api/token/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/clear/', CookieTokenClearView.as_view(), name='token_clear'),
    path('api/dashboard/', DashboardAPIView.as_view(), name='api-dashboard'),
    path('api/dashboard/executivo/', ExecutiveBIDashboardAPIView.as_view(), name='api-dashboard-executivo'),
    path('api/investimentos/dashboard/', DashboardInvestimentoAPIView.as_view(), name='api-investimentos-dashboard'),
    path('api/relatorios/dre/', RelatoriosDREAPIView.as_view(), name='api-relatorios-dre'),
    # Ferramentas
    path('api/ferramentas/importar/', FerramentasImportarAPIView.as_view(), name='api-ferramentas-importar'),
    path('api/ferramentas/importar-extrato/', FerramentasImportarExtratoAPIView.as_view(), name='api-ferramentas-importar-extrato'),
    path('api/ferramentas/conciliacao/', FerramentasConciliacaoListAPIView.as_view(), name='api-ferramentas-conciliacao'),
    path('api/ferramentas/conciliacao/processar/', FerramentasConciliacaoProcessarAPIView.as_view(), name='api-ferramentas-conciliacao-processar'),
    path('api/ferramentas/exportar/', FerramentasExportarAPIView.as_view(), name='api-ferramentas-exportar'),
]



