"""ViewSets da REST API para Gestão e Simulações de Investimento.

Controla requisições HTTP associadas ao patrimônio de renda fixa e variável do usuário.
Registra os endpoints para manuseio da árvore de classes, categorias de ativos,
controle de ordens (compras, vendas e proventos), emissão do painel de controle do investidor
e cálculos em tempo real de reequilíbrio e balanceamento inteligente de aportes.
"""

from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from .models import Ativo, Transacao, ClasseAtivo, SubcategoriaAtivo, CategoriaAtivo
from .serializers import (
    ClasseAtivoSerializer,
    CategoriaAtivoSerializer,
    SubcategoriaAtivoSerializer,
    AtivoSerializer,
    TransacaoInvestimentoSerializer
)
from .services.dashboard_service import DashboardInvestimentoService


class ClasseAtivoViewSet(viewsets.ModelViewSet):
    """ViewSet REST para operações de CRUD de ClasseAtivo do investidor.

    Atribui isolamento por usuário autenticado.
    """
    serializer_class = ClasseAtivoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna as macro classes de ativos pertencentes ao usuário logado.

        Returns:
            QuerySet: Classes de ativos do usuário.
        """
        return ClasseAtivo.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        """Atribui o usuário proprietário no momento do cadastro.

        Args:
            serializer (Serializer): Serializador com dados validados.
        """
        serializer.save(usuario=self.request.user)


class CategoriaAtivoViewSet(viewsets.ModelViewSet):
    """ViewSet REST para operações de CRUD de CategoriaAtivo do investidor.

    Garante integridade e isolamento multi-tenant básico.
    """
    serializer_class = CategoriaAtivoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna as categorias de ativos do usuário autenticado.

        Returns:
            QuerySet: Categorias de ativos.
        """
        return CategoriaAtivo.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        """Salva a associação do usuário logado na nova categoria de ativos.

        Args:
            serializer (Serializer): Serializador da categoria.
        """
        serializer.save(usuario=self.request.user)


class SubcategoriaAtivoViewSet(viewsets.ModelViewSet):
    """ViewSet REST para operações de CRUD de SubcategoriaAtivo do investidor.

    Segmentação final (folha) da árvore de ativos.
    """
    serializer_class = SubcategoriaAtivoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna as subcategorias de ativos do usuário logado.

        Returns:
            QuerySet: Subcategorias de ativos.
        """
        return SubcategoriaAtivo.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        """Salva a associação do usuário autenticado na subcategoria de ativos.

        Args:
            serializer (Serializer): Serializador da subcategoria.
        """
        serializer.save(usuario=self.request.user)


class AtivoViewSet(viewsets.ModelViewSet):
    """ViewSet REST completo para gestão de Ativos de Renda Fixa ou Renda Variável.

    Controla tickers, indexadores, limites de alocação e expõe ação de sincronismo de cotações.
    """
    serializer_class = AtivoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna os ativos cadastrados pertencentes ao usuário logado.

        Returns:
            QuerySet: Ativos do usuário.
        """
        return Ativo.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        """Salva o ativo e inicializa a posição de compra inaugural se declarada na requisição.

        Facilita o cadastro criando atomaticamente a primeira transação de compra
        caso 'quantidade_inicial' e 'preco_medio_inicial' sejam providos.

        Args:
            serializer (Serializer): Serializador de ativos.
        """
        # Primeiro, salva o ativo
        ativo = serializer.save(usuario=self.request.user)
        
        # Processa posição inicial se fornecida no body da requisição
        qtd_inicial = self.request.data.get("quantidade_inicial")
        preco_inicial = self.request.data.get("preco_medio_inicial")
        data_compra = self.request.data.get("data_compra")

        if qtd_inicial and preco_inicial:
            try:
                qtd = Decimal(str(qtd_inicial))
                preco = Decimal(str(preco_inicial))
                if qtd > 0:
                    Transacao.objects.create(
                        usuario=self.request.user,
                        ativo=ativo,
                        tipo=Transacao.TIPO_COMPRA,
                        data=data_compra or timezone.now().date(),
                        quantidade=qtd,
                        preco_unitario=preco,
                        valor_total=qtd * preco,
                    )
            except Exception:
                pass  # Tolera falha na transação inicial silenciosamente

    @action(detail=False, methods=['post'], url_path='atualizar-cotacoes')
    def atualizar_cotacoes(self, request) -> Response:
        """Ação global que dispara o coletor de cotações B3 atualizadas via Screener.

        Args:
            request (Request): Requisição HTTP.

        Returns:
            Response: Dicionário contendo estatísticas de cotações atualizadas ou falhas.
        """
        from .calculators import atualizar_cotacoes as run_atualizar_cotacoes
        count, errors = run_atualizar_cotacoes()
        return Response({
            "count": count,
            "errors": errors
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='atualizar')
    def atualizar(self, request, pk=None) -> Response:
        """Busca o histórico de cotações dos últimos 30 dias no Yahoo Finance para este ativo e atualiza no banco.
        """
        ativo = self.get_object()
        ticker = (ativo.ticker or "").strip().upper()
        if not ticker:
            return Response(
                {"error": "Este ativo não possui um ticker cadastrado para atualização de cotações."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Heurística para formatar o ticker do Yahoo Finance
        # Se for um ticker fracionário da B3 (ex: PETR4F, PRIO3F), removemos o 'F' final
        # para consultar a cotação do lote padrão no Yahoo Finance (que é idêntica).
        normalized_ticker = ticker
        if len(normalized_ticker) >= 2 and normalized_ticker[-1] == "F" and normalized_ticker[-2].isdigit():
            normalized_ticker = normalized_ticker[:-1]

        # Se terminar com número (dígito), e não tiver "." nem ":"
        if normalized_ticker[-1].isdigit() and "." not in normalized_ticker and ":" not in normalized_ticker:
            normalized_ticker = f"{normalized_ticker}.SA"

        import urllib.request
        import json
        from decimal import Decimal
        import datetime

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{normalized_ticker}?range=30d&interval=1d"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            return Response(
                {"error": f"Erro de comunicação com Yahoo Finance: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        chart_data = res_data.get("chart", {})
        result_list = chart_data.get("result")
        if not result_list:
            error_description = chart_data.get("error", {}).get("description", "Ticker não encontrado ou sem cotações disponíveis.")
            return Response(
                {"error": f"Erro retornado pelo Yahoo Finance: {error_description}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = result_list[0]
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {})
        quote_list = indicators.get("quote", [{}])
        close_prices = quote_list[0].get("close", [])

        if not timestamps or not close_prices:
            return Response(
                {"error": "Nenhuma cotação encontrada no histórico do Yahoo Finance para o período."},
                status=status.HTTP_400_BAD_REQUEST
            )

        count = 0
        from .models import Cotacao
        for ts, close in zip(timestamps, close_prices):
            if close is None:
                continue
            try:
                # Converte o timestamp UTC para date local
                dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).date()
                Cotacao.objects.update_or_create(
                    ativo=ativo,
                    data=dt,
                    defaults={"valor": Decimal(str(close))}
                )
                count += 1
            except Exception:
                pass

        return Response({
            "count": count,
            "message": f"Histórico de {count} cotações atualizado com sucesso."
        }, status=status.HTTP_200_OK)



class TransacaoInvestimentoViewSet(viewsets.ModelViewSet):
    """ViewSet REST para controle de ordens e lançamentos da carteira do usuário.

    Aplica recálculos matemáticos para determinar o valor líquido total consolidado de
    compra, venda e recebimentos de dividendos/JCP.
    """
    serializer_class = TransacaoInvestimentoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna o histórico de transações de investimento pertencentes ao usuário logado.

        Returns:
            QuerySet: Transações de investimentos do usuário.
        """
        queryset = Transacao.objects.filter(usuario=self.request.user)
        ativo_id = self.request.query_params.get("ativo")
        if ativo_id:
            queryset = queryset.filter(ativo_id=ativo_id)
        return queryset

    def perform_create(self, serializer):
        """Salva a ordem calculando o valor total de aquisição de forma estruturada.

        Garante o acréscimo de taxas/corretagem nas compras, abatimento de taxas
        nas vendas e limitação de quantidade unitária (1) para recebimentos de proventos.

        Args:
            serializer (Serializer): Serializador da transação.
        """
        tipo = self.request.data.get("tipo")
        qtd = Decimal(str(self.request.data.get("quantidade", 1)))
        preco = Decimal(str(self.request.data.get("preco_unitario", 0)))
        taxas = Decimal(str(self.request.data.get("taxas", 0)))
        
        # Lógica de cálculo do valor total baseado no tipo
        if tipo == Transacao.TIPO_DIVIDENDO:
            qtd = Decimal("1")
            taxas = Decimal("0")
            valor_total = preco
        elif tipo == Transacao.TIPO_COMPRA:
            valor_total = (qtd * preco) + taxas
        elif tipo == Transacao.TIPO_VENDA:
            valor_total = (qtd * preco) - taxas
        else:
            valor_total = qtd * preco
            
        serializer.save(
            usuario=self.request.user,
            quantidade=qtd,
            preco_unitario=preco,
            taxas=taxas,
            valor_total=valor_total
        )

    def perform_update(self, serializer):
        """Atualiza a ordem recalculando o valor total de aquisição de forma estruturada.

        Garante o acréscimo de taxas/corretagem nas compras, abatimento de taxas
        nas vendas e limitação de quantidade unitária (1) para recebimentos de proventos.

        Args:
            serializer (Serializer): Serializador da transação.
        """
        tipo = self.request.data.get("tipo", serializer.instance.tipo)
        
        qtd_raw = self.request.data.get("quantidade")
        qtd = Decimal(str(qtd_raw)) if qtd_raw is not None else serializer.instance.quantidade
        
        preco_raw = self.request.data.get("preco_unitario")
        preco = Decimal(str(preco_raw)) if preco_raw is not None else serializer.instance.preco_unitario
        
        taxas_raw = self.request.data.get("taxas")
        taxas = Decimal(str(taxas_raw)) if taxas_raw is not None else serializer.instance.taxas

        # Lógica de cálculo do valor total baseado no tipo
        if tipo == Transacao.TIPO_DIVIDENDO:
            qtd = Decimal("1")
            taxas = Decimal("0")
            valor_total = preco
        elif tipo == Transacao.TIPO_COMPRA:
            valor_total = (qtd * preco) + taxas
        elif tipo == Transacao.TIPO_VENDA:
            valor_total = (qtd * preco) - taxas
        else:
            valor_total = qtd * preco

        serializer.save(
            quantidade=qtd,
            preco_unitario=preco,
            taxas=taxas,
            valor_total=valor_total
        )


class DashboardInvestimentoAPIView(APIView):
    """Endpoint consolidado que alimenta a tela de investimentos do React.

    Agrega dados patrimoniais totais, valor investido em carteira, rentabilidade acumulada
    a mercado, proventos recebidos, séries de alocação por classes/categorias e
    históricos de performance e vencimentos de Renda Fixa.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Processa a requisição GET retornando o payload estruturado do dashboard de investimentos.

        Args:
            request (Request): Requisição HTTP contendo 'page' na query string.

        Returns:
            Response: Dicionário completo de séries de alocação, performance e cotações.
        """
        page = request.GET.get("page", 1)
        service = DashboardInvestimentoService(request.user)
        dados = service.obter_dados_dashboard(page)
        
        # Serializar objetos complexos do Django no dicionário retornado pelo service
        ativos_serialized = AtivoSerializer(dados["ativos"], many=True).data
        top_5_serialized = AtivoSerializer(dados["top_5_ativos"], many=True).data
        top_rent_serialized = AtivoSerializer(dados["top_rentabilidade"], many=True).data
        upcoming_serialized = AtivoSerializer(dados["proximos_vencimentos"], many=True).data
        
        ultima_t = dados["ultima_transacao"]
        ultima_serialized = None
        if ultima_t:
            ultima_serialized = TransacaoInvestimentoSerializer(ultima_t).data
            
        payload = {
            "total_patrimonio": float(dados["total_patrimonio"]),
            "total_investido": float(dados["total_investido"]),
            "total_rentabilidade": float(dados["total_rentabilidade"]),
            "total_rentabilidade_percentual": float(dados["total_rentabilidade_percentual"]),
            "total_dividendos": float(dados["total_dividendos"]),
            "alocacao_classes": {
                "labels": dados["allocation_labels"],
                "valores": dados["allocation_values"],
            },
            "alocacao_categorias": {
                "labels": dados["category_labels"],
                "valores": dados["category_values"],
            },
            "ativos": ativos_serialized,
            "top_5_ativos": top_5_serialized,
            "top_rentabilidade": top_rent_serialized,
            "ultima_transacao": ultima_serialized,
            "proximos_vencimentos": upcoming_serialized,
            "performance_monthly": dados["performance_monthly"],
            "performance_yearly": dados["performance_yearly"],
        }
        
        return Response(payload, status=status.HTTP_200_OK)


