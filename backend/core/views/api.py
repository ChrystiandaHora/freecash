"""
ViewSets da REST API para Lançamentos Financeiros e Dashboard.

Contém a inteligência que processa requisições HTTP do frontend React, aplicando
regras rígidas de isolamento de usuário autenticado (IsAuthenticated) e chamando
serviços de apoio para cadastros em lote, liquidação e consolidação de gráficos.
"""

import calendar
from datetime import date
from dateutil.relativedelta import relativedelta

from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Categoria, Conta, CartaoCredito
from core.serializers import CategoriaSerializer, ContaSerializer, CartaoCreditoSerializer, CustomTokenObtainPairSerializer
from core.services.dashboard_helper import (
    totals_for_range_competencia,
    pct_change,
    serie_por_dia_competencia,
    serie_fluxo_projetado_competencia,
    breakdown_despesas_competencia,
    resumo_ultimos_3_meses_competencia,
    clamp_int,
    make_periodo,
    make_periodo_custom
)

class CategoriaViewSet(viewsets.ModelViewSet):
    """ViewSet REST para operações de CRUD de Categoria financeira do usuário.

    Garante o isolamento por usuário autenticado.
    """
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna o conjunto de categorias pertencentes ao usuário autenticado.

        Returns:
            QuerySet: Filtro de categorias do usuário.
        """
        return Categoria.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        """Salva a nova categoria atribuindo o usuário autenticado da requisição.

        Args:
            serializer (Serializer): Instância do serializador da categoria.
        """
        serializer.save(usuario=self.request.user)


class CartaoCreditoViewSet(viewsets.ModelViewSet):
    """ViewSet REST para operações de CRUD do modelo CartaoCredito.

    Garante acesso apenas a cartões ativos do usuário proprietário.
    """
    serializer_class = CartaoCreditoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna os cartões de crédito ativos vinculados ao usuário autenticado.

        Returns:
            QuerySet: Cartões ativos do usuário.
        """
        return CartaoCredito.objects.filter(usuario=self.request.user, ativo=True)

    def perform_create(self, serializer):
        """Associa o usuário autenticado como proprietário ao criar o cartão.

        Args:
            serializer (Serializer): Instância do serializador do cartão.
        """
        serializer.save(usuario=self.request.user)


class ContaViewSet(viewsets.ModelViewSet):
    """ViewSet REST para operações padrão de CRUD de Conta (lançamentos financeiros).

    Permite filtragem opcional por tipo (Receita/Despesa) e por estado de liquidação.
    """
    serializer_class = ContaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna as contas do usuário autenticado aplicando filtros dinâmicos de query.

        Query Params suportados:
            tipo (str, optional): 'R' para receita, 'D' para despesa, 'I' para investimentos.
            realizada (str, optional): 'true'/'1' ou 'false'/'0' para estado de liquidação.

        Returns:
            QuerySet: Contas filtradas do usuário.
        """
        queryset = Conta.objects.filter(usuario=self.request.user)
        tipo = self.request.query_params.get('tipo')
        realizada = self.request.query_params.get('realizada')
        
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if realizada is not None:
            realizada_bool = realizada.lower() in ['true', '1']
            queryset = queryset.filter(transacao_realizada=realizada_bool)
            
        return queryset

    def perform_create(self, serializer):
        """Salva a nova conta associando-a ao usuário autenticado.

        Args:
            serializer (Serializer): Serializador da conta contendo dados validados.
        """
        serializer.save(usuario=self.request.user)


class DashboardAPIView(APIView):
    """Endpoint unificado que alimenta o painel de controle principal (Dashboard) do React.

    Calcula e formata agregados diários, séries mensais projetadas de fluxo de caixa,
    distribuição de gastos por categoria e balanço de status de contas (pagas/atrasadas).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Processa a requisição GET retornando o payload completo do dashboard financeiro.

        Args:
            request (Request): Requisição HTTP contendo parâmetros opcionais de mês/ano.

        Returns:
            Response: Dicionário contendo estatísticas, séries temporais e listas do dashboard.
        """
        usuario = request.user
        hoje = timezone.localdate()

        mes_raw = request.GET.get("mes")
        ano_raw = request.GET.get("ano")

        if mes_raw and ano_raw:
            try:
                mes = int(mes_raw)
                ano = int(ano_raw)
                if 1 <= mes <= 12 and 1900 <= ano <= 2100:
                    periodo = make_periodo_custom(ano, mes)
                else:
                    raise ValueError
            except ValueError:
                periodo = make_periodo(hoje, 0)
        else:
            periodo_idx = clamp_int(request.GET.get("periodo"), default=0, min_v=0, max_v=2)
            periodo = make_periodo(hoje, periodo_idx)

        # Totais do período por COMPETÊNCIA (data_prevista)
        total_receitas, total_despesas = totals_for_range_competencia(
            usuario, periodo.inicio, periodo.fim
        )
        saldo_mes = total_receitas - total_despesas

        # Comparação vs mês anterior também por COMPETÊNCIA
        receitas_prev, despesas_prev = totals_for_range_competencia(
            usuario, periodo.inicio_prev, periodo.inicio
        )
        receitas_pct = pct_change(total_receitas, receitas_prev)
        despesas_pct = pct_change(total_despesas, despesas_prev)

        # Séries diárias por COMPETÊNCIA
        dias_labels, receitas_dias = serie_por_dia_competencia(
            usuario, Conta.TIPO_RECEITA, periodo.inicio, periodo.fim, periodo.ultimo_dia
        )
        _, despesas_dias = serie_por_dia_competencia(
            usuario, Conta.TIPO_DESPESA, periodo.inicio, periodo.fim, periodo.ultimo_dia
        )

        # Séries 6 meses Projetadas (Janela: -2, -1, 0, +1, +2, +3)
        meses_labels, receitas_6m = serie_fluxo_projetado_competencia(
            usuario, Conta.TIPO_RECEITA, periodo.inicio
        )
        _, despesas_6m = serie_fluxo_projetado_competencia(
            usuario, Conta.TIPO_DESPESA, periodo.inicio
        )
        saldos_6m = [r - d for r, d in zip(receitas_6m, despesas_6m)]

        # Breakdown por COMPETÊNCIA
        breakdown_items, top_categoria = breakdown_despesas_competencia(
            usuario, periodo.inicio, periodo.fim, total_despesas, top_n=4
        )

        media_gasto_dia = (
            (total_despesas / periodo.ultimo_dia) if periodo.ultimo_dia else 0.0
        )
        taxa_poupanca = (
            (saldo_mes / total_receitas * 100.0) if total_receitas > 0 else None
        )

        # Card "Status das contas" continua por data_prevista
        contas_mes = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            data_prevista__gte=periodo.inicio,
            data_prevista__lt=periodo.fim,
        ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

        contas_pendentes = contas_mes.filter(transacao_realizada=False).count()
        contas_pagas = contas_mes.filter(transacao_realizada=True).count()
        contas_atrasadas = contas_mes.filter(
            transacao_realizada=False, data_prevista__lt=hoje
        ).count()

        # Próximas contas (inclui atrasadas, ordenadas por vencimento)
        upcoming_bills = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=False,
            )
            .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
            .select_related("categoria")
            .order_by("data_prevista")[:5]
        )

        # Transações recentes continuam por CAIXA (realizadas)
        ultimas_transacoes = (
            Conta.objects.filter(usuario=usuario, transacao_realizada=True)
            .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
            .select_related("categoria")
            .order_by("-data_realizacao", "-id")[:7]
        )

        resumo_3_meses = resumo_ultimos_3_meses_competencia(usuario, periodo.inicio)
        saldo_prev = receitas_prev - despesas_prev
        saldo_pct = pct_change(saldo_mes, saldo_prev)

        # Serialização das listas
        upcoming_serialized = ContaSerializer(upcoming_bills, many=True).data
        recentes_serialized = ContaSerializer(ultimas_transacoes, many=True).data

        payload = {
            "periodo": periodo.idx,
            "periodo_label": periodo.label,
            "hoje": str(hoje),
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
            "saldo_mes": saldo_mes,
            "receitas_pct": receitas_pct,
            "despesas_pct": despesas_pct,
            "saldo_pct": saldo_pct,
            "media_gasto_dia": media_gasto_dia,
            "taxa_poupanca": taxa_poupanca,
            "contas_pagas": contas_pagas,
            "contas_pendentes": contas_pendentes,
            "contas_atrasadas": contas_atrasadas,
            "grafico_diario": {
                "labels": dias_labels,
                "receitas": receitas_dias,
                "despesas": despesas_dias,
            },
            "grafico_projetado": {
                "labels": meses_labels,
                "receitas": receitas_6m,
                "despesas": despesas_6m,
                "saldos": saldos_6m,
            },
            "breakdown_despesas": breakdown_items,
            "top_categoria": top_categoria,
            "proximas_contas": upcoming_serialized,
            "ultimas_transacoes": recentes_serialized,
            "resumo_3_meses": resumo_3_meses,
        }

        return Response(payload, status=status.HTTP_200_OK)


from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

class CookieTokenObtainPairView(TokenObtainPairView):
    """View customizada de autenticação JWT SimpleJWT.

    Realiza o login do usuário gerando tokens de acesso (retornado no payload JSON)
    e de atualização (refresh token, configurado em um cookie seguro HttpOnly).
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs) -> Response:
        """Gera os tokens JWT e define o refresh token em um cookie HttpOnly seguro.

        Args:
            request (Request): Requisição contendo as credenciais (username, password).

        Returns:
            Response: Dicionário contendo o token de acesso (access token).
        """
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.detail)
            
        data = serializer.validated_data
        response_data = {
            "access": data["access"]
        }
        response = Response(response_data, status=status.HTTP_200_OK)
        
        # Set the refresh token in HttpOnly cookie
        refresh_token = data["refresh"]
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=7 * 24 * 60 * 60, # 7 days
            path="/api/token/refresh/",
        )
        return response

class CookieTokenRefreshView(TokenRefreshView):
    """View customizada para renovação de token JWT.

    Extrai o refresh token do cookie seguro HttpOnly ou do corpo da requisição,
    validando-o para gerar e retornar um novo token de acesso (access token).
    """

    def post(self, request, *args, **kwargs) -> Response:
        """Processa a renovação do token de acesso utilizando o refresh token do cookie.

        Args:
            request (Request): Requisição contendo cookies ou dados do refresh token.

        Returns:
            Response: Novo token de acesso gerado.
        """
        # Extract refresh token from cookies
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            # check body just in case
            refresh_token = request.data.get("refresh")
            
        if not refresh_token:
            return Response({"detail": "Refresh token not found in cookies or body."}, status=status.HTTP_400_BAD_REQUEST)
            
        data = {"refresh": refresh_token}
        serializer = self.get_serializer(data=data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.detail)
            
        data = serializer.validated_data
        response_data = {
            "access": data["access"]
        }
        response = Response(response_data, status=status.HTTP_200_OK)
        
        # If SimpleJWT rotated the refresh token, set the new one in the cookie
        new_refresh = data.get("refresh")
        if new_refresh:
            response.set_cookie(
                key="refresh_token",
                value=new_refresh,
                httponly=True,
                secure=False,
                samesite="Lax",
                max_age=7 * 24 * 60 * 60,
                path="/api/token/refresh/",
            )
        return response

class CookieTokenClearView(APIView):
    """Endpoint responsável pelo logout do usuário no sistema.

    Limpa e deleta o cookie HttpOnly do refresh token para invalidar a sessão ativa.
    """
    permission_classes = []
    def post(self, request) -> Response:
        """Remove o cookie seguro de refresh token, encerrando a autenticação.

        Args:
            request (Request): Requisição de logout.

        Returns:
            Response: Confirmação de logout bem-sucedido.
        """
        response = Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
        response.delete_cookie("refresh_token", path="/api/token/refresh/")
        return response


from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from core.services.criar_usuario import criar_usuario_com_ecosistema

class RegistrationAPIView(APIView):
    """Endpoint responsável pela criação e registro de novos usuários no FreeCash.

    Realiza validações de senhas, evita duplicação de usernames e cria o
    ecossistema financeiro básico (categorias iniciais) em uma transação atômica.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs) -> Response:
        """Cria um novo usuário, gera suas credenciais e retorna os tokens JWT iniciais.

        Args:
            request (Request): Requisição com username, password e confirm.

        Returns:
            Response: Token de acesso e cookie HttpOnly do refresh token.
        """
        username = request.data.get("username")
        password = request.data.get("password")
        confirm = request.data.get("confirm")

        if not username or not password or not confirm:
            return Response(
                {"detail": "Todos os campos (usuário, senha e confirmação de senha) são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        username = username.strip()

        if len(password) < 6:
            return Response(
                {"detail": "A senha deve ter no mínimo 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if password != confirm:
            return Response(
                {"detail": "As senhas não coincidem."},
                status=status.HTTP_400_BAD_REQUEST
            )

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response(
                {"detail": "Este nome de usuário já está em uso."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                user = criar_usuario_com_ecosistema(username, password)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['username'] = user.username
            response_data = {
                "access": str(refresh.access_token)
            }
            response = Response(response_data, status=status.HTTP_201_CREATED)
            
            # Set the refresh token in HttpOnly cookie
            response.set_cookie(
                key="refresh_token",
                value=str(refresh),
                httponly=True,
                secure=False,
                samesite="Lax",
                max_age=7 * 24 * 60 * 60, # 7 days
                path="/api/token/refresh/",
            )
            return response
        except Exception as e:
            return Response(
                {"detail": f"Erro interno ao criar usuário: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ─── Integrated REST Endpoints for React Frontend ─────────────────────────────
from decimal import Decimal
from rest_framework.decorators import action
from core.serializers import (
    ContasPagarAPISerializer,
    ReceitasAPISerializer,
    TransacaoAPISerializer,
    CartaoCreditoAPISerializer
)

class CartaoCreditoAPIViewSet(viewsets.ModelViewSet):
    """ViewSet especializado de cartões de crédito para consumo direto do React.

    Serve dados estáticos de limites e informações agregadas como compras recentes.
    """
    serializer_class = CartaoCreditoAPISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna os cartões de crédito ativos pertencentes ao usuário autenticado.

        Returns:
            QuerySet: Lista de cartões ativos.
        """
        return CartaoCredito.objects.filter(usuario=self.request.user, ativo=True)

    def perform_create(self, serializer):
        """Salva a associação do usuário logado ao criar um novo cartão.

        Args:
            serializer (Serializer): Serializador do cartão.
        """
        serializer.save(usuario=self.request.user)


class ContasPagarViewSet(viewsets.ModelViewSet):
    """ViewSet especializado no gerenciamento de Despesas (Contas a Pagar).

    Disponibiliza CRUD adaptado para o frontend do React, suportando mapeamentos
    de campos personalizados de vencimento e ações customizadas de liquidação e lote.
    """
    serializer_class = ContasPagarAPISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filtra as despesas do usuário logado no período especificado de mês e ano.

        Returns:
            QuerySet: Lançamentos de despesas do usuário no mês e ano selecionados.
        """
        # Accounts payable = Despesas Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
        queryset = Conta.objects.filter(
            usuario=self.request.user,
            tipo=Conta.TIPO_DESPESA
        ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

        # Se for uma ação de detalhe (detalhar, editar, deletar), não filtra por mês/ano
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            return queryset.order_by('-data_prevista')

        mes = self.request.query_params.get('mes')
        ano = self.request.query_params.get('ano')

        if not mes or not ano:
            from django.utils import timezone
            today = timezone.localdate()
            if not mes:
                mes = today.month
            if not ano:
                ano = today.year

        try:
            mes = int(mes)
            ano = int(ano)
            queryset = queryset.filter(data_prevista__month=mes, data_prevista__year=ano)
        except (ValueError, TypeError):
            pass

        return queryset.order_by('-data_prevista')

    def perform_create(self, serializer):
        """Salva a associação do usuário logado ao criar a despesa.

        Args:
            serializer (Serializer): Serializador da conta.
        """
        serializer.save(usuario=self.request.user)

    def perform_update(self, serializer):
        """Garante a associação do usuário ao atualizar a despesa.

        Args:
            serializer (Serializer): Serializador da conta.
        """
        serializer.save(usuario=self.request.user)

    def create(self, request, *args, **kwargs) -> Response:
        """Customiza a criação resolvendo a categoria pelo nome em string e mapeando a data de vencimento.

        Args:
            request (Request): Requisição contendo os dados da despesa.

        Returns:
            Response: A despesa criada serializada.
        """
        data = request.data.copy()
        
        # 1. Map data_vencimento -> data_prevista
        if 'data_vencimento' in data:
            data['data_prevista'] = data['data_vencimento']
            
        # 2. Resolve or create category name string
        categoria_nome = data.get('categoria')
        if categoria_nome:
            categoria_obj, _ = Categoria.objects.get_or_create(
                usuario=request.user,
                nome=categoria_nome.strip(),
                tipo=Categoria.TIPO_DESPESA
            )
            data['categoria'] = categoria_obj.id
            
        # 3. Enforce tipo = Despesa
        data['tipo'] = Conta.TIPO_DESPESA
        
        # Validate using standard serializer
        serializer = ContaSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        response_serializer = ContasPagarAPISerializer(serializer.instance, context={'request': request})
        headers = self.get_success_headers(serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs) -> Response:
        """Customiza a atualização mapeando categoria pelo nome e data de vencimento.

        Args:
            request (Request): Dados da modificação.

        Returns:
            Response: Despesa atualizada serializada.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data.copy()
        
        # 1. Map data_vencimento -> data_prevista
        if 'data_vencimento' in data:
            data['data_prevista'] = data['data_vencimento']
            
        # 2. Resolve or create category name string
        categoria_nome = data.get('categoria')
        if categoria_nome:
            categoria_obj, _ = Categoria.objects.get_or_create(
                usuario=request.user,
                nome=categoria_nome.strip(),
                tipo=Categoria.TIPO_DESPESA
            )
            data['categoria'] = categoria_obj.id
            
        # Validate using standard serializer
        serializer = ContaSerializer(instance, data=data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        response_serializer = ContasPagarAPISerializer(serializer.instance, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put'])
    def pagar(self, request, pk=None) -> Response:
        """Liquida a despesa marcando-a como paga na data atual.

        Args:
            request (Request): Requisição HTTP.
            pk (str, optional): ID da conta.

        Returns:
            Response: Despesa paga serializada.
        """
        conta = self.get_object()
        conta.marcar_realizada()
        return Response(ContasPagarAPISerializer(conta, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='lote')
    def lote(self, request) -> Response:
        """Registra múltiplos lançamentos de despesa simultaneamente de forma atômica.

        Args:
            request (Request): Requisição contendo 'itens' (lista de despesas) e 'todas_pagas'.

        Returns:
            Response: Confirmação do total de despesas criadas ou lista detalhada de erros.
        """
        usuario = request.user
        itens = request.data.get('itens', [])
        todas_pagas = request.data.get('todas_pagas', False)
        
        if not isinstance(itens, list) or not itens:
            return Response({"detail": "Uma lista de itens é necessária."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Find default expense category
        default_cat = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA, is_default=True
        ).first()
        
        if not default_cat:
            default_cat = Categoria.objects.filter(
                usuario=usuario, tipo=Categoria.TIPO_DESPESA
            ).first()
            
        contas_para_criar = []
        erros = []
        
        for idx, item in enumerate(itens, 1):
            desc = item.get('descricao', '').strip()
            val_raw = item.get('valor')
            dt_raw = item.get('data_vencimento', '').strip()
            
            # Skip completely empty lines
            if not desc and val_raw is None and not dt_raw:
                continue
                
            if not desc:
                erros.append(f"Linha {idx}: Descrição é obrigatória.")
                continue
            if val_raw is None or str(val_raw).strip() == '':
                erros.append(f"Linha {idx}: Valor é obrigatório.")
                continue
            if not dt_raw:
                erros.append(f"Linha {idx}: Data é obrigatória.")
                continue
                
            try:
                # Parse valor
                val_str = str(val_raw).replace('.', '').replace(',', '.') if ',' in str(val_raw) else str(val_raw)
                valor = Decimal(val_str).quantize(Decimal("0.01"))
                if valor <= 0:
                    erros.append(f"Linha {idx}: Valor deve ser maior que zero.")
                    continue
            except Exception:
                erros.append(f"Linha {idx}: Valor inválido.")
                continue
                
            try:
                # Parse date
                from datetime import datetime
                data_parsed = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        data_parsed = datetime.strptime(dt_raw, fmt).date()
                        break
                    except ValueError:
                        continue
                if not data_parsed:
                    erros.append(f"Linha {idx}: Data inválida. Use AAAA-MM-DD.")
                    continue
            except Exception:
                erros.append(f"Linha {idx}: Data inválida.")
                continue
                
            # If the item specifies a custom category name, let's create/fetch it
            cat_nome = item.get('categoria', '').strip()
            if cat_nome:
                categoria_obj, _ = Categoria.objects.get_or_create(
                    usuario=usuario,
                    nome=cat_nome,
                    tipo=Categoria.TIPO_DESPESA
                )
            else:
                categoria_obj = default_cat
                
            contas_para_criar.append(
                Conta(
                    usuario=usuario,
                    tipo=Conta.TIPO_DESPESA,
                    descricao=desc,
                    valor=valor,
                    data_prevista=data_parsed,
                    categoria=categoria_obj,
                    transacao_realizada=todas_pagas,
                    data_realizacao=data_parsed if todas_pagas else None
                )
            )
            
        if erros:
            return Response({"erros": erros}, status=status.HTTP_400_BAD_REQUEST)
            
        if not contas_para_criar:
            return Response({"detail": "Nenhum lançamento preenchido."}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            Conta.objects.bulk_create(contas_para_criar)
            
        return Response({"msg": f"{len(contas_para_criar)} contas registradas com sucesso!"}, status=status.HTTP_201_CREATED)


class ReceitasViewSet(viewsets.ModelViewSet):
    """ViewSet especializado no gerenciamento de Receitas (Contas a Receber).

    Controla lançamentos de entrada financeira do usuário, filtrados por período mensal.
    """
    serializer_class = ReceitasAPISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filtra as receitas do usuário logado no período especificado de mês e ano.

        Returns:
            QuerySet: Receitas filtradas do usuário.
        """
        queryset = Conta.objects.filter(
            usuario=self.request.user,
            tipo=Conta.TIPO_RECEITA
        )

        # Se for uma ação de detalhe (detalhar, editar, deletar), não filtra por mês/ano
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            return queryset.order_by('-data_prevista')

        mes = self.request.query_params.get('mes')
        ano = self.request.query_params.get('ano')

        if not mes or not ano:
            from django.utils import timezone
            today = timezone.localdate()
            if not mes:
                mes = today.month
            if not ano:
                ano = today.year

        try:
            mes = int(mes)
            ano = int(ano)
            queryset = queryset.filter(data_prevista__month=mes, data_prevista__year=ano)
        except (ValueError, TypeError):
            pass

        return queryset.order_by('-data_prevista')

    def perform_create(self, serializer):
        """Salva a associação do usuário logado ao criar a receita.

        Args:
            serializer (Serializer): Serializador da receita.
        """
        serializer.save(usuario=self.request.user)

    def perform_update(self, serializer):
        """Salva o usuário autenticado na receita atualizada.

        Args:
            serializer (Serializer): Serializador de atualização.
        """
        serializer.save(usuario=self.request.user)

    def create(self, request, *args, **kwargs) -> Response:
        """Customiza a criação mapeando a data de recebimento e resolvendo a categoria.

        Args:
            request (Request): Dados da nova receita.

        Returns:
            Response: Receita criada serializada.
        """
        data = request.data.copy()
        
        # 1. Map data_recebimento -> data_prevista
        if 'data_recebimento' in data:
            data['data_prevista'] = data['data_recebimento']
            
        # 2. Resolve or create category name string
        categoria_nome = data.get('categoria')
        if categoria_nome:
            categoria_obj, _ = Categoria.objects.get_or_create(
                usuario=request.user,
                nome=categoria_nome.strip(),
                tipo=Categoria.TIPO_RECEITA
            )
            data['categoria'] = categoria_obj.id
            
        # 3. Enforce tipo = Receita
        data['tipo'] = Conta.TIPO_RECEITA
        
        # Validate using standard serializer
        serializer = ContaSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        response_serializer = ReceitasAPISerializer(serializer.instance, context={'request': request})
        headers = self.get_success_headers(serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs) -> Response:
        """Customiza a atualização mapeando categoria pelo nome e data de recebimento.

        Args:
            request (Request): Dados da modificação.

        Returns:
            Response: Receita atualizada serializada.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data.copy()
        
        # 1. Map data_recebimento -> data_prevista
        if 'data_recebimento' in data:
            data['data_prevista'] = data['data_recebimento']
            
        # 2. Resolve or create category name string
        categoria_nome = data.get('categoria')
        if categoria_nome:
            categoria_obj, _ = Categoria.objects.get_or_create(
                usuario=request.user,
                nome=categoria_nome.strip(),
                tipo=Categoria.TIPO_RECEITA
            )
            data['categoria'] = categoria_obj.id

        # 3. Enforce tipo = Receita
        data['tipo'] = Conta.TIPO_RECEITA
            
        # Validate using standard serializer
        serializer = ContaSerializer(instance, data=data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        response_serializer = ReceitasAPISerializer(serializer.instance, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class TransacoesViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet unificado para visualização do extrato de transações.

    Retorna transações liquidadas (despesas pagas) e entradas de receita ativas,
    ordenando por data de ocorrência real.
    """
    serializer_class = TransacaoAPISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna despesas pagas e receitas no mês e ano selecionados com anotação dinâmica.

        Returns:
            QuerySet: Lançamentos liquidados do usuário de competência/caixa.
        """
        # 1. Base queryset: exclude credit card invoices and filter by user
        queryset = Conta.objects.filter(
            usuario=self.request.user,
            eh_fatura_cartao=False
        )

        # 2. Exclude unpaid bills (only keep revenues OR paid bills)
        queryset = queryset.filter(
            Q(tipo=Conta.TIPO_RECEITA) | 
            Q(tipo=Conta.TIPO_DESPESA, transacao_realizada=True)
        )

        mes = self.request.query_params.get('mes')
        ano = self.request.query_params.get('ano')

        if not mes or not ano:
            from django.utils import timezone
            today = timezone.localdate()
            if not mes:
                mes = today.month
            if not ano:
                ano = today.year

        # 3. Annotate with dynamic transaction date (data_realizacao if paid, else data_prevista)
        queryset = queryset.annotate(
            data_transacao=Coalesce('data_realizacao', 'data_prevista')
        )

        try:
            mes = int(mes)
            ano = int(ano)
            # 4. Filter using the annotated dynamic transaction date
            queryset = queryset.filter(
                data_transacao__month=mes,
                data_transacao__year=ano
            )
        except (ValueError, TypeError):
            pass

        return queryset.order_by('-data_transacao', '-id')


class RelatoriosDREAPIView(APIView):
    """Endpoint responsável pela emissão simplificada do relatório de DRE (Demonstração do Resultado do Exercício).

    Emite agregados anuais consolidados contendo o somatório de receitas,
    despesas fixas e variáveis, rentabilidade e dividendos acumulados da carteira.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Calcula e formata os dados anuais da DRE.

        Args:
            request (Request): Requisição HTTP contendo 'ano' na query string.

        Returns:
            Response: Payload JSON estruturado com DRE anual de receitas, despesas e investimentos.
        """
        usuario = request.user
        ano = request.GET.get('ano')
        if not ano:
            ano = timezone.localdate().year
        else:
            try:
                ano = int(ano)
            except ValueError:
                ano = timezone.localdate().year

        # Receitas
        receitas_qs = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            data_prevista__year=ano
        )
        total_receitas = receitas_qs.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

        # Despesas
        despesas_qs = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            data_prevista__year=ano,
            eh_fatura_cartao=False
        )
        despesas_fixas = despesas_qs.filter(cartao__isnull=True).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        despesas_variaveis = despesas_qs.filter(cartao__isnull=False).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

        # Investimentos (Dividendos / Rentabilidade)
        dividendos = Decimal('0.00')
        rentabilidade = Decimal('0.00')
        try:
            from investimento.models import Transacao as InvTransacao
            dividendos = InvTransacao.objects.filter(
                usuario=usuario,
                tipo=InvTransacao.TIPO_DIVIDENDO,
                data__year=ano
            ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')

            from investimento.services.dashboard_service import DashboardInvestimentoService
            inv_service = DashboardInvestimentoService(usuario)
            inv_data = inv_service.obter_dados_dashboard()
            rentabilidade = Decimal(str(inv_data.get("total_rentabilidade", 0.0)))
        except Exception:
            pass

        # Sazonalidade / Mapa de Calor de Gastos dos últimos 6 meses (26 semanas)
        import datetime
        hoje_dt = timezone.localdate()
        seis_meses_atras = hoje_dt - datetime.timedelta(days=180)
        
        gastos_qs = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            data_prevista__gte=seis_meses_atras,
            data_prevista__lte=hoje_dt
        )
        
        dias_semana_nomes = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        grid = {d: [0.0] * 26 for d in range(7)}
        semana_labels = []
        for w in range(26):
            semana_inicio = seis_meses_atras + datetime.timedelta(weeks=w)
            semana_labels.append(semana_inicio.strftime("%d/%m"))
            
        for gasto in gastos_qs:
            dt_gasto = gasto.data_prevista
            dias_diff = (dt_gasto - seis_meses_atras).days
            week_idx = dias_diff // 7
            if 0 <= week_idx < 26:
                day_idx = dt_gasto.weekday()
                grid[day_idx][week_idx] += float(gasto.valor)
                
        heatmap_series = []
        for d in range(7):
            data_points = []
            for w in range(26):
                data_points.append({
                    "x": semana_labels[w],
                    "y": round(grid[d][w], 2)
                })
            heatmap_series.append({
                "name": dias_semana_nomes[d],
                "data": data_points
            })

        payload = {
            "receitas": {
                "total_receitas": float(total_receitas),
                "deducoes": 0.0,
            },
            "despesas": {
                "despesas_fixas": float(despesas_fixas),
                "despesas_variaveis": float(despesas_variaveis),
                "total_despesas": float(despesas_fixas + despesas_variaveis),
            },
            "investimentos": {
                "dividendos": float(dividendos),
                "rentabilidade": float(rentabilidade),
            },
            "sazonalidade": {
                "series": heatmap_series
            }
        }
        return Response(payload, status=status.HTTP_200_OK)


class ExecutiveBIDashboardAPIView(APIView):
    """Endpoint unificado para o Dashboard Executivo / BI.

    Agrega o histórico patrimonial mensal dos últimos 12 meses, consolidando a liquidez 
    física (caixa acumulado) com a custódia de investimentos (avaliação a mercado),
    permitindo traçar a curva real de evolução do patrimônio líquido (Net Worth).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Calcula e formata a série mensal e indicadores de saúde patrimonial do usuário.

        Args:
            request (Request): Requisição HTTP.

        Returns:
            Response: Dicionário contendo labels de meses, séries de liquidez, custódia, DRE e KPIs.
        """
        from datetime import datetime
        from investimento.services.carteira_historico_service import CarteiraHistoricoService
        usuario = request.user
        
        # 1. Certifica que os snapshots de investimentos estão atualizados
        inv_service = CarteiraHistoricoService(usuario)
        inv_service.atualizar()
        
        # 2. Obtém a série mensal de investimentos filtrando pela quantidade de meses
        meses_param = request.GET.get('meses')
        if meses_param:
            if meses_param.lower() == 'all':
                meses_val = None
            else:
                try:
                    meses_val = int(meses_param)
                except ValueError:
                    meses_val = 12
        else:
            meses_val = 12

        series_inv = inv_service.series_mensal(meses=meses_val)
        
        # Se não houver histórico de investimentos, gera os últimos N meses com base em hoje
        if not series_inv:
            from dateutil.relativedelta import relativedelta
            hoje = timezone.localdate()
            series_inv = []
            limit_months = meses_val if meses_val is not None else 12
            for i in range(limit_months - 1, -1, -1):
                d = hoje - relativedelta(months=i)
                ultimo_dia_mes = calendar.monthrange(d.year, d.month)[1]
                series_inv.append({
                    "data": f"{d.year}-{d.month:02d}-{ultimo_dia_mes:02d}",
                    "patrimonio": 0.0,
                    "investido": 0.0
                })
        
        meses_labels = []
        liquidez_values = []
        custodia_values = []
        patrimonio_liquido_values = []
        
        meses_nomes_pt = [
            "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
            "Jul", "Ago", "Set", "Out", "Nov", "Dez"
        ]
        
        for item in series_inv:
            dt_str = item["data"]
            dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
            
            # Label ex: "Set/25"
            label = f"{meses_nomes_pt[dt.month]}/{str(dt.year)[2:]}"
            meses_labels.append(label)
            
            # Custódia (Investimento a mercado)
            custodia = float(item.get("patrimonio", 0))
            custodia_values.append(custodia)
            
            # Liquidez Física (Acumulado de caixa até este mês)
            contas_filtro = Conta.objects.filter(
                usuario=usuario,
                transacao_realizada=True,
                data_realizacao__lte=dt
            ).filter(
                Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
            )
            
            receitas = float(contas_filtro.filter(tipo=Conta.TIPO_RECEITA).aggregate(s=Coalesce(Sum('valor'), Decimal('0.0'))).get('s') or 0.0)
            despesas = float(contas_filtro.filter(tipo=Conta.TIPO_DESPESA).aggregate(s=Coalesce(Sum('valor'), Decimal('0.0'))).get('s') or 0.0)
            liquidez = receitas - despesas
            liquidez_values.append(liquidez)
            
            # Patrimônio Líquido Real = Liquidez Física + Custódia
            patrimonio_liquido_values.append(liquidez + custodia)
            
        # Evolução mensal do patrimônio líquido
        evolucao_mensal = [0.0]
        for i in range(1, len(patrimonio_liquido_values)):
            evolucao_mensal.append(patrimonio_liquido_values[i] - patrimonio_liquido_values[i-1])
            
        # DRE resumida e aportes dos últimos 12 meses
        tabela_dre = []
        proventos_acumulados_series = []
        for item in series_inv:
            dt_str = item["data"]
            dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
            label = f"{meses_nomes_pt[dt.month]}/{str(dt.year)[2:]}"
            
            # Receitas e Despesas ocorridas DE FATO dentro deste mês
            contas_mes = Conta.objects.filter(
                usuario=usuario,
                transacao_realizada=True,
                data_realizacao__year=dt.year,
                data_realizacao__month=dt.month
            ).filter(
                Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
            )
            
            rec_mes = float(contas_mes.filter(tipo=Conta.TIPO_RECEITA).aggregate(s=Coalesce(Sum('valor'), Decimal('0.0'))).get('s') or 0.0)
            desp_mes = float(contas_mes.filter(tipo=Conta.TIPO_DESPESA).aggregate(s=Coalesce(Sum('valor'), Decimal('0.0'))).get('s') or 0.0)
            saldo_mes = rec_mes - desp_mes
            
            # Aportes em investimentos efetuados no mês
            from investimento.models import Transacao as TransacaoInv
            compras_mes = float(TransacaoInv.objects.filter(
                usuario=usuario,
                tipo=TransacaoInv.TIPO_COMPRA,
                data__year=dt.year,
                data__month=dt.month
            ).aggregate(s=Coalesce(Sum('valor_total'), Decimal('0.0'))).get('s') or 0.0)
            
            vendas_mes = float(TransacaoInv.objects.filter(
                usuario=usuario,
                tipo=TransacaoInv.TIPO_VENDA,
                data__year=dt.year,
                data__month=dt.month
            ).aggregate(s=Coalesce(Sum('valor_total'), Decimal('0.0'))).get('s') or 0.0)
            
            aportes_mes = compras_mes - vendas_mes

            # Proventos recebidos no mês
            proventos_mes = float(TransacaoInv.objects.filter(
                usuario=usuario,
                tipo=TransacaoInv.TIPO_DIVIDENDO,
                data__year=dt.year,
                data__month=dt.month
            ).aggregate(s=Coalesce(Sum('valor_total'), Decimal('0.0'))).get('s') or 0.0)

            # Proventos acumulados até este mês (Snowball)
            proventos_acum_mes = float(TransacaoInv.objects.filter(
                usuario=usuario,
                tipo=TransacaoInv.TIPO_DIVIDENDO,
                data__lte=dt
            ).aggregate(s=Coalesce(Sum('valor_total'), Decimal('0.0'))).get('s') or 0.0)
            
            proventos_acumulados_series.append(proventos_acum_mes)
            
            tabela_dre.append({
                "mes": label,
                "receitas": rec_mes,
                "despesas": desp_mes,
                "saldo": saldo_mes,
                "aportes": aportes_mes,
                "proventos": proventos_mes,
                "proventos_acumulados": proventos_acum_mes
            })
            
        # Métricas Consolidadas / KPIs
        total_liquidez = liquidez_values[-1] if liquidez_values else 0.0
        total_custodia = custodia_values[-1] if custodia_values else 0.0
        total_patrimonio_liquido = patrimonio_liquido_values[-1] if patrimonio_liquido_values else 0.0
        
        # Saving Rate médio
        saving_rates = []
        for row in tabela_dre:
            if row["receitas"] > 0:
                saving_rates.append((row["saldo"] / row["receitas"]) * 100.0)
        saving_rate_medio = sum(saving_rates) / len(saving_rates) if saving_rates else 0.0
        
        payload = {
            "meses": meses_labels,
            "liquidez": liquidez_values,
            "custodia": custodia_values,
            "patrimonio_liquido": patrimonio_liquido_values,
            "proventos_acumulados": proventos_acumulados_series,
            "evolucao_mensal": evolucao_mensal,
            "tabela_dre": tabela_dre[::-1],  # Mais recente primeiro para a tabela do UI
            "kpis": {
                "total_liquidez": total_liquidez,
                "total_custodia": total_custodia,
                "total_patrimonio_liquido": total_patrimonio_liquido,
                "saving_rate_medio": saving_rate_medio
            }
        }
        return Response(payload, status=status.HTTP_200_OK)


