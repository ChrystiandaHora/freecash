"""Mapeamento de rotas da API REST do FreeCash.

Registra os roteadores do DRF e os endpoints de sessão JWT por cookie, dashboard,
relatórios e ferramentas de conciliação.

Barramento de APIs:
    /api/token/ ......... Controle de sessão JWT (obter, renovar, encerrar).
    /api/auth/ .......... Registro, verificação de e-mail e senha.
    /api/admin/ ......... Painel administrativo da plataforma.
    /api/dashboard/ ..... Agregados estatísticos mensais.
    /api/financeiro/ .... Despesas, receitas, transações e cartões.
    /api/planejamento/ .. Horizonte de saldos e calendário.
    /api/investimentos/ . Carteira e simulador de balanceamento.
    /api/ferramentas/ ... Importação de extrato, conciliação e exportação.
"""


from django.conf import settings
from django.contrib import admin
from django.urls import path, include

urlpatterns = []

# O admin do Django fica exposto apenas em desenvolvimento. Nenhum modelo está
# registrado nele (core/admin.py e investimento/admin.py estão vazios) e a
# administração da plataforma é feita pelo painel React sobre /api/admin/ — manter
# a rota em produção seria oferecer um formulário de login a mais para atacar, sem
# entregar nada em troca.
if settings.DEBUG:
    urlpatterns += [path("admin/", admin.site.urls)]

# REST API Routing Configuration
from rest_framework.routers import DefaultRouter
from core.views.api import (
    CategoriaViewSet, CartaoCreditoViewSet, ContaViewSet, DashboardAPIView,
    CookieTokenObtainPairView, CookieTokenRefreshView, CookieTokenClearView,
    CartaoCreditoAPIViewSet, ContasPagarViewSet, ReceitasViewSet,
    TransacoesViewSet, RelatoriosDREAPIView,
    ExecutiveBIDashboardAPIView, ComprasCartaoViewSet, SaldoAtualAPIView,
    MetaFinanceiraViewSet, PlanoMetasAPIView
)
from core.views.auth_api import (
    EmailVerifyConfirmAPIView,
    EmailVerifyResendAPIView,
    MeAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    RegistrationAPIView,
)
from investimento.views_api import (
    ClasseAtivoViewSet, CategoriaAtivoViewSet, SubcategoriaAtivoViewSet,
    AtivoViewSet, CarteiraViewSet, PosicaoCarteiraViewSet,
    TransacaoInvestimentoViewSet, DashboardInvestimentoAPIView, BalanceamentoAPIView
)
from core.views.health import HealthCheckAPIView
from core.views.conta_api import (
    EncerrarOutrasSessoesAPIView,
    ExcluirContaAPIView,
    PerfilAPIView,
    SessoesAPIView,
    TrocaEmailCancelarAPIView,
    TrocaEmailConfirmarAPIView,
    TrocaEmailSolicitarAPIView,
    TrocaSenhaAPIView,
)
from core.views.planejamento_api import (
    CalendarioPagamentosAPIView,
    DesfazerLiquidacaoAPIView,
    HorizonteSaldosAPIView,
    LiquidarLancamentoAPIView,
)
from core.views.admin_api import (
    AdminLogsAPIView,
    AdminMetricasAPIView,
    AdminReativarUsuarioAPIView,
    AdminSuspenderUsuarioAPIView,
    AdminUsuarioDetalheAPIView,
    AdminUsuariosListAPIView,
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
router.register(r'financeiro/metas', MetaFinanceiraViewSet, basename='api-financeiro-metas')

router.register(r'investimentos/carteiras', CarteiraViewSet, basename='api-carteira')
router.register(r'investimentos/posicoes', PosicaoCarteiraViewSet, basename='api-posicao-carteira')
router.register(r'investimentos/classes', ClasseAtivoViewSet, basename='api-classe')
router.register(r'investimentos/categorias', CategoriaAtivoViewSet, basename='api-categoria-ativo')
router.register(r'investimentos/subcategorias', SubcategoriaAtivoViewSet, basename='api-subcategoria')
router.register(r'investimentos/ativos', AtivoViewSet, basename='api-ativo')
router.register(r'investimentos/transacoes', TransacaoInvestimentoViewSet, basename='api-transacao-investimento')
router.register(r'configuracoes/contas-bancarias', ContasBancariasViewSet, basename='api-contas-bancarias')

# REST API & Token paths
urlpatterns += [
    path('api/', include(router.urls)),
    path('api/health/', HealthCheckAPIView.as_view(), name='api-health'),
    path('api/register/', RegistrationAPIView.as_view(), name='api-register'),
    path('api/token/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/clear/', CookieTokenClearView.as_view(), name='token_clear'),
    # Identidade: estado da conta, confirmação de e-mail e redefinição de senha.
    path('api/auth/me/', MeAPIView.as_view(), name='api-auth-me'),
    path('api/auth/verificar-email/', EmailVerifyConfirmAPIView.as_view(),
         name='api-auth-verificar-email'),
    path('api/auth/verificar-email/reenviar/', EmailVerifyResendAPIView.as_view(),
         name='api-auth-verificar-email-reenviar'),
    path('api/auth/senha/reset/', PasswordResetRequestAPIView.as_view(),
         name='api-auth-senha-reset'),
    path('api/auth/senha/reset/confirmar/', PasswordResetConfirmAPIView.as_view(),
         name='api-auth-senha-reset-confirmar'),
    # Painel administrativo. Todas as rotas exigem IsAdminPlataforma e expõem
    # somente metadados de conta — nunca dado financeiro de usuário.
    path('api/admin/usuarios/', AdminUsuariosListAPIView.as_view(),
         name='api-admin-usuarios'),
    path('api/admin/usuarios/<int:pk>/', AdminUsuarioDetalheAPIView.as_view(),
         name='api-admin-usuario-detalhe'),
    path('api/admin/usuarios/<int:pk>/suspender/',
         AdminSuspenderUsuarioAPIView.as_view(), name='api-admin-usuario-suspender'),
    path('api/admin/usuarios/<int:pk>/reativar/',
         AdminReativarUsuarioAPIView.as_view(), name='api-admin-usuario-reativar'),
    path('api/admin/metricas/', AdminMetricasAPIView.as_view(),
         name='api-admin-metricas'),
    path('api/admin/logs/', AdminLogsAPIView.as_view(), name='api-admin-logs'),
    # Conta do próprio usuário: perfil, credenciais e exclusão.
    path('api/auth/perfil/', PerfilAPIView.as_view(), name='api-auth-perfil'),
    path('api/auth/email/alterar/', TrocaEmailSolicitarAPIView.as_view(),
         name='api-auth-email-alterar'),
    path('api/auth/email/alterar/cancelar/', TrocaEmailCancelarAPIView.as_view(),
         name='api-auth-email-alterar-cancelar'),
    path('api/auth/email/alterar/confirmar/', TrocaEmailConfirmarAPIView.as_view(),
         name='api-auth-email-alterar-confirmar'),
    path('api/auth/senha/alterar/', TrocaSenhaAPIView.as_view(),
         name='api-auth-senha-alterar'),
    path('api/auth/conta/excluir/', ExcluirContaAPIView.as_view(),
         name='api-auth-conta-excluir'),
    path('api/auth/sessoes/', SessoesAPIView.as_view(), name='api-auth-sessoes'),
    path('api/auth/sessoes/encerrar-outras/', EncerrarOutrasSessoesAPIView.as_view(),
         name='api-auth-sessoes-encerrar-outras'),
    # Planejamento: projeção de saldo e agenda de pagamentos/recebimentos.
    path('api/planejamento/horizonte-saldos/', HorizonteSaldosAPIView.as_view(),
         name='api-planejamento-horizonte'),
    path('api/planejamento/calendario/', CalendarioPagamentosAPIView.as_view(),
         name='api-planejamento-calendario'),
    path('api/planejamento/lancamentos/<int:pk>/liquidar/',
         LiquidarLancamentoAPIView.as_view(), name='api-planejamento-liquidar'),
    path('api/planejamento/lancamentos/<int:pk>/desfazer/',
         DesfazerLiquidacaoAPIView.as_view(), name='api-planejamento-desfazer'),
    path('api/saldo-atual/', SaldoAtualAPIView.as_view(), name='api-saldo-atual'),
    path('api/dashboard/', DashboardAPIView.as_view(), name='api-dashboard'),
    path('api/dashboard/executivo/', ExecutiveBIDashboardAPIView.as_view(), name='api-dashboard-executivo'),
    path('api/investimentos/dashboard/', DashboardInvestimentoAPIView.as_view(), name='api-investimentos-dashboard'),
    path('api/investimentos/balanceamento/', BalanceamentoAPIView.as_view(), name='api-investimentos-balanceamento'),
    path('api/relatorios/dre/', RelatoriosDREAPIView.as_view(), name='api-relatorios-dre'),
    # Irmão de `financeiro/metas/` no router: um sub-path colidiria com o detail `metas/<pk>/`.
    path('api/financeiro/metas-plano/', PlanoMetasAPIView.as_view(), name='api-financeiro-metas-plano'),
    # Ferramentas
    path('api/ferramentas/importar/', FerramentasImportarAPIView.as_view(), name='api-ferramentas-importar'),
    path('api/ferramentas/importar-extrato/', FerramentasImportarExtratoAPIView.as_view(), name='api-ferramentas-importar-extrato'),
    path('api/ferramentas/conciliacao/', FerramentasConciliacaoListAPIView.as_view(), name='api-ferramentas-conciliacao'),
    path('api/ferramentas/conciliacao/processar/', FerramentasConciliacaoProcessarAPIView.as_view(), name='api-ferramentas-conciliacao-processar'),
    path('api/ferramentas/exportar/', FerramentasExportarAPIView.as_view(), name='api-ferramentas-exportar'),
]



