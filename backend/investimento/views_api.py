"""ViewSets da REST API para Gestão e Simulações de Investimento.

Controla requisições HTTP associadas ao patrimônio de renda fixa e variável do usuário.
Registra os endpoints para manuseio da árvore de classes, categorias de ativos,
controle de ordens (compras, vendas e proventos), emissão do painel de controle do investidor
e cálculos em tempo real de reequilíbrio e balanceamento inteligente de aportes.
"""

import uuid as uuid_lib
from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction as db_transaction
from django.db.models import (
    Count, DecimalField, Exists, ExpressionWrapper, F, OuterRef, Prefetch, Q, Sum,
)
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Ativo,
    Carteira,
    PosicaoCarteira,
    Transacao,
    ClasseAtivo,
    SubcategoriaAtivo,
    CategoriaAtivo,
)
from .serializers import (
    ClasseAtivoSerializer,
    CategoriaAtivoSerializer,
    SubcategoriaAtivoSerializer,
    AtivoSerializer,
    CarteiraSerializer,
    PosicaoCarteiraSerializer,
    TransacaoInvestimentoSerializer,
    TransferenciaSerializer,
)
from .services.dashboard_service import DashboardInvestimentoService


def carteira_do_request(request) -> int | None:
    """Lê o filtro `?carteira=` da querystring, se houver.

    Ausente devolve `None`, e a chamada responde o consolidado. Um valor que não é
    número levanta 400: engolir o erro e responder o consolidado tornava
    `?carteira=abc` indistinguível de "sem filtro", e um typo na querystring passaria
    por resposta legítima.

    O id **não** é validado contra o usuário aqui — de propósito. Quem consome aplica
    o filtro depois de `filter(usuario=...)`, então uma carteira alheia devolve vazio.
    Responder 404 nesse caso transformaria o endpoint num oráculo que confirma se
    aquele id existe na base de outra pessoa.

    Returns:
        int | None: Id da carteira pedida, ou None para o consolidado.

    Raises:
        ValidationError: Quando `?carteira=` não é um número inteiro.
    """
    valor = request.query_params.get("carteira")
    if not valor:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValidationError(
            {"carteira": "Informe o id numérico da carteira, ou omita para o consolidado."}
        )


class CarteiraViewSet(viewsets.ModelViewSet):
    """ViewSet REST para CRUD das carteiras (custódias) do usuário.

    Carteira com histórico não é excluída: `destroy` recusa com 409 e aponta o
    arquivamento (`ativa=False`), preservando as ordens já lançadas. A guarda vive aqui,
    e não como `PROTECT` no schema — no banco ela quebrava a exclusão de conta exigida
    pela LGPD, porque o coletor do Django a encontra ao percorrer `User -> Carteira`.
    """
    serializer_class = CarteiraSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna as carteiras do usuário logado.

        Returns:
            QuerySet: Carteiras do usuário, com as arquivadas incluídas por padrão.
        """
        # Anotado no queryset, não em method field: lá seria uma consulta por carteira
        custo = ExpressionWrapper(
            F("posicoes__quantidade") * F("posicoes__preco_medio"),
            output_field=DecimalField(max_digits=19, decimal_places=4),
        )
        queryset = Carteira.objects.filter(usuario=self.request.user).annotate(
            valor_investido=Coalesce(Sum(custo), Decimal(0)),
            ativos_com_posicao=Count(
                "posicoes", filter=Q(posicoes__quantidade__gt=0), distinct=True
            ),
            # `Exists` em vez de `obj.transacoes.exists()` no serializer: aquele era
            # uma consulta por carteira, e a tela lista todas de uma vez.
            tem_transacoes=Exists(
                Transacao.objects.filter(carteira=OuterRef("pk"))
            ),
        )
        if self.request.query_params.get("ativas") in ("1", "true"):
            queryset = queryset.filter(ativa=True)
        return queryset

    def perform_create(self, serializer):
        """Salva a carteira vinculada ao usuário autenticado."""
        serializer.save(usuario=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Recusa a exclusão de carteira que ainda guarda ordens.

        Excluir levaria as transações junto e apagaria histórico de rentabilidade
        em silêncio. A resposta aponta o arquivamento como caminho.
        """
        carteira = self.get_object()
        if carteira.transacoes.exists():
            return Response(
                {
                    "detail": (
                        "Esta carteira tem ordens registradas e não pode ser excluída. "
                        "Arquive-a para tirá-la dos filtros sem perder o histórico."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class PosicaoCarteiraViewSet(
    viewsets.mixins.ListModelMixin,
    viewsets.mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Leitura das posições por carteira e escrita da meta de alocação.

    Só lista e atualiza: criar ou apagar posição é consequência de lançar ordens, não
    uma ação direta — o recálculo é quem materializa as linhas.
    """
    serializer_class = PosicaoCarteiraSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna as posições do usuário, opcionalmente de uma carteira só.

        Returns:
            QuerySet: Posições em carteira do usuário.
        """
        queryset = PosicaoCarteira.objects.filter(
            usuario=self.request.user
        ).select_related("carteira", "ativo")
        carteira_id = carteira_do_request(self.request)
        if carteira_id:
            queryset = queryset.filter(carteira_id=carteira_id)
        # Simétrico ao `?ativo=` das transações; sem ele o detalhe baixava tudo e filtrava no cliente
        ativo_id = self.request.query_params.get("ativo")
        if ativo_id:
            queryset = queryset.filter(ativo_id=ativo_id)
        return queryset


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
        """Atribui o usuário proprietário no momento do cadastro."""
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
        """Salva a associação do usuário logado na nova categoria de ativos."""
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
        """Salva a associação do usuário autenticado na subcategoria de ativos."""
        serializer.save(usuario=self.request.user)


class AtivoViewSet(viewsets.ModelViewSet):
    """ViewSet REST completo para gestão de Ativos de Renda Fixa ou Renda Variável.

    Controla tickers, indexadores, limites de alocação e expõe ação de sincronismo de cotações.
    """
    serializer_class = AtivoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna os ativos do usuário, restritos a uma carteira quando pedido.

        Com `?carteira=`, devolve apenas os ativos com posição aberta naquela custódia
        e carrega a posição correspondente, para que o serializador possa reportar a
        quantidade e o preço médio **daquela** carteira em vez dos consolidados.

        Returns:
            QuerySet: Ativos do usuário.
        """
        queryset = Ativo.objects.filter(usuario=self.request.user)

        carteira_id = carteira_do_request(self.request)
        if carteira_id:
            queryset = queryset.filter(
                posicoes__carteira_id=carteira_id, posicoes__quantidade__gt=0
            ).prefetch_related(
                Prefetch(
                    "posicoes",
                    queryset=PosicaoCarteira.objects.filter(carteira_id=carteira_id),
                    to_attr="posicao_filtrada",
                )
            )
        return queryset

    def get_serializer_context(self) -> dict:
        """Informa ao serializador se a resposta está escopada a uma carteira.

        Returns:
            dict: Contexto padrão do DRF acrescido de `carteira_id`.
        """
        context = super().get_serializer_context()
        context["carteira_id"] = carteira_do_request(self.request)
        return context

    def perform_create(self, serializer):
        """Salva o ativo e inicializa a posição de compra inaugural se declarada na requisição.

        Facilita o cadastro criando atomaticamente a primeira transação de compra
        caso 'quantidade_inicial' e 'preco_medio_inicial' sejam providos.
        """
        # Primeiro, salva o ativo
        ativo = serializer.save(usuario=self.request.user)

        # Processa posição inicial se fornecida no body da requisição
        qtd_inicial = self.request.data.get("quantidade_inicial")
        preco_inicial = self.request.data.get("preco_medio_inicial")
        data_compra = self.request.data.get("data_compra")
        carteira = self._carteira_da_compra_inicial()

        if qtd_inicial and preco_inicial and carteira:
            try:
                qtd = Decimal(str(qtd_inicial))
                preco = Decimal(str(preco_inicial))
                if qtd > 0:
                    Transacao.objects.create(
                        usuario=self.request.user,
                        ativo=ativo,
                        carteira=carteira,
                        tipo=Transacao.TIPO_COMPRA,
                        data=data_compra or timezone.now().date(),
                        quantidade=qtd,
                        preco_unitario=preco,
                        valor_total=qtd * preco,
                    )
            except Exception:
                pass  # Tolera falha na transação inicial silenciosamente
        elif carteira:
            try:
                PosicaoCarteira.objects.get_or_create(
                    usuario=self.request.user,
                    ativo=ativo,
                    carteira=carteira,
                    defaults={"quantidade": Decimal("0"), "custo_total": Decimal("0")},
                )
            except Exception:
                pass

    def _carteira_da_compra_inicial(self) -> Carteira | None:
        """Resolve em qual custódia entra a compra inaugural.

        Usa a carteira enviada no corpo; sem ela, cai na primeira carteira ativa do
        usuário. O fallback existe para não quebrar o cadastro de quem nunca separou
        por corretora e tem só a Carteira Padrão.

        Returns:
            Carteira | None: Carteira de destino, ou None se o usuário não tiver nenhuma.
        """
        carteiras = Carteira.objects.filter(usuario=self.request.user)
        carteira_id = self.request.data.get("carteira")
        if carteira_id:
            return carteiras.filter(pk=carteira_id).first()
        return carteiras.filter(ativa=True).first()

    @action(detail=False, methods=['post'], url_path='atualizar-cotacoes')
    def atualizar_cotacoes(self, request) -> Response:
        """Ação global que dispara o coletor de cotações B3 atualizadas via Screener.

        Returns:
            Response: Dicionário contendo estatísticas de cotações atualizadas ou falhas.
        """
        from .calculators import atualizar_cotacoes as run_atualizar_cotacoes
        # Escopado ao usuário autenticado. Sem o argumento, a função percorre os
        # ativos de toda a base: além de gravar cotações de terceiros, a lista de
        # erros devolvida aqui traria os tickers dos outros usuários, expondo a
        # composição das carteiras deles.
        count, errors = run_atualizar_cotacoes(usuario=request.user)
        return Response({
            "count": count,
            "errors": errors
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='atualizar')
    def atualizar(self, request, pk=None) -> Response:
        """Busca 30 dias de cotações no Yahoo Finance e grava no banco."""
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
        carteira_id = carteira_do_request(self.request)
        if carteira_id:
            queryset = queryset.filter(carteira_id=carteira_id)
        return queryset

    @action(detail=False, methods=['post'], url_path='transferir')
    def transferir(self, request) -> Response:
        """Move cotas de uma carteira para outra, sem realizar lucro.

        Grava as duas pernas (`TS` e `TE`) no mesmo `grupo_transferencia`, dentro de
        uma transação de banco: meia transferência gravada faria cotas sumirem ou
        aparecerem do nada.

        O preço carregado é o preço médio da carteira de origem no momento — assim o
        custo total do usuário fecha igual antes e depois, e o preço médio fiscal
        (consolidado) não se move.

        Returns:
            Response: As duas ordens criadas, ou os erros de validação.
        """
        serializer = TransferenciaSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        posicao = dados['posicao_origem']
        quantidade = dados['quantidade']
        data = dados.get('data') or timezone.now().date()
        preco = posicao.preco_medio
        grupo = uuid_lib.uuid4()

        comum = {
            "usuario": request.user,
            "ativo": dados['ativo'],
            "data": data,
            "quantidade": quantidade,
            "preco_unitario": preco,
            "taxas": Decimal(0),
            "valor_total": quantidade * preco,
            "grupo_transferencia": grupo,
        }

        with db_transaction.atomic():
            saida = Transacao.objects.create(
                carteira=dados['origem'], tipo=Transacao.TIPO_TRANSF_SAIDA, **comum
            )
            entrada = Transacao.objects.create(
                carteira=dados['destino'], tipo=Transacao.TIPO_TRANSF_ENTRADA, **comum
            )

        payload = TransacaoInvestimentoSerializer(
            [saida, entrada], many=True, context={'request': request}
        ).data
        return Response(payload, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        """Apaga a transferência inteira quando uma das pernas é excluída.

        Deixar a perna oposta sobrevivendo sozinha criaria ou destruiria cotas: a
        saída sem a entrada some com o papel, a entrada sem a saída o duplica.
        """
        if instance.grupo_transferencia:
            Transacao.objects.filter(
                usuario=instance.usuario,
                grupo_transferencia=instance.grupo_transferencia,
            ).delete()
            return
        instance.delete()

    def perform_create(self, serializer):
        """Salva a ordem calculando o valor total de aquisição de forma estruturada.

        Garante o acréscimo de taxas/corretagem nas compras, abatimento de taxas
        nas vendas e limitação de quantidade unitária (1) para recebimentos de proventos.
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

    Agrega patrimônio, valor investido, rentabilidade a mercado, proventos e as séries
    de alocação por categoria e por carteira que a tela desenha.

    O payload carrega só o que a tela lê. Ele já trouxe a lista completa de ativos, os
    top 5 por valor e por rentabilidade, os próximos vencimentos e a última ordem —
    nenhum consumido, e cada bloco custava uma serialização de `AtivoSerializer`, que
    por ativo busca 30 cotações. Voltar a incluí-los exige uma tela que os use.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve o payload do dashboard de investimentos.

        Returns:
            Response: Dicionário completo de séries de alocação, performance e cotações.
        """
        carteira_id = carteira_do_request(request)
        service = DashboardInvestimentoService(request.user, carteira_id)
        dados = service.obter_dados_dashboard()

        payload = {
            "total_patrimonio": float(dados["total_patrimonio"]),
            "total_investido": float(dados["total_investido"]),
            "total_rentabilidade": float(dados["total_rentabilidade"]),
            "total_rentabilidade_percentual": float(dados["total_rentabilidade_percentual"]),
            "total_dividendos": float(dados["total_dividendos"]),
            "alocacao_categorias": {
                "labels": dados["category_labels"],
                "valores": dados["category_values"],
            },
            "alocacao_carteiras": {
                "labels": dados["carteira_labels"],
                "valores": dados["carteira_values"],
            },
            "carteira_filtrada": carteira_id,
            "performance_monthly": dados["performance_monthly"],
            "rentabilidade_mensal": dados["rentabilidade_mensal"],
        }
        
        return Response(payload, status=status.HTTP_200_OK)


class BalanceamentoAPIView(APIView):
    """Calcula o balanceamento e o reequilíbrio da carteira.

    Trabalha em dois níveis, porque com múltiplas custódias "quanto comprar" tem duas
    respostas: quanto aportar **em cada corretora** (metas de `Carteira`) e quanto
    comprar de cada ativo **dentro de uma** (metas de `PosicaoCarteira`).

    O plano por ativo é sempre de uma carteira só — sem `?carteira=`, vem vazio com
    `carteira: None`, e a tela pede uma seleção. Somar as metas de todas daria 100%
    vezes o número de carteiras, e a soma que a tela valida deixaria de significar
    alguma coisa.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Gera e retorna o plano de balanceamento e distribuição de aportes.

        Returns:
            Response: Total de patrimônio, plano por ativo na carteira em foco e plano
                entre carteiras.
        """
        carteira = self._carteira_em_foco(request)
        if carteira is None:
            return Response(
                {
                    "total_patrimonio": 0.0,
                    "soma_metas": 0.0,
                    "classes": [],
                    "carteiras": self._plano_entre_carteiras(request.user),
                    "carteira": None,
                },
                status=status.HTTP_200_OK,
            )

        posicoes = (
            PosicaoCarteira.objects.filter(
                usuario=request.user, carteira=carteira, ativo__ativo=True
            )
            .select_related("ativo__subcategoria__categoria__classe")
            .order_by("ativo__ticker")
        )

        total_patrimonio = sum(p.valor_investido for p in posicoes)

        ativos_por_classe = {}
        soma_metas = 0.0

        for posicao in posicoes:
            ativo = posicao.ativo
            classe_obj = ativo.subcategoria.categoria.classe if (ativo.subcategoria and ativo.subcategoria.categoria) else None
            classe_nome = classe_obj.nome if classe_obj else "Outros"

            if classe_nome not in ativos_por_classe:
                ativos_por_classe[classe_nome] = {
                    "nome": classe_nome,
                    "ativos": [],
                    "soma_classe": 0.0
                }

            valor_atual = float(posicao.valor_investido)
            meta = float(posicao.meta_porcentagem)
            soma_metas += meta
            ativos_por_classe[classe_nome]["soma_classe"] += meta

            perc_atual = (valor_atual / float(total_patrimonio) * 100) if total_patrimonio > 0 else 0.0
            valor_ideal = (meta / 100.0) * float(total_patrimonio)
            diferenca = valor_ideal - valor_atual

            valor_mercado = float(posicao.valor_total_atual)
            rentabilidade = valor_mercado - valor_atual

            ativos_por_classe[classe_nome]["ativos"].append({
                "id": ativo.id,
                "posicao_id": posicao.id,
                "ticker": ativo.ticker,
                "nome": ativo.nome,
                "meta_porcentagem": meta,
                "valor_atual": valor_atual,
                "perc_atual": perc_atual,
                "preco_atual": float(ativo.cotacao_atual or 0),
                "rentabilidade": rentabilidade,
                "rentabilidade_perc": (rentabilidade / valor_atual * 100) if valor_atual else 0.0,
                "valor_ideal": valor_ideal,
                "diferenca": diferenca,
            })

        payload = {
            "total_patrimonio": float(total_patrimonio),
            "soma_metas": soma_metas,
            "classes": list(ativos_por_classe.values()),
            "carteira": CarteiraSerializer(carteira).data,
            "carteiras": self._plano_entre_carteiras(request.user),
        }

        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request) -> Response:
        """Atualiza em lote as metas de alocação, por ativo e/ou por carteira.

        Aceita `metas` (itens `{"ativo": id, "meta": n}`, na carteira em foco) e
        `carteiras` (itens `{"id": id, "meta": n}`). Por compatibilidade, um item de
        `metas` sem `ativo` tem seu `id` lido como id de ativo.

        Returns:
            Response: Confirmação de sucesso ou relatório parcial de falhas.
        """
        metas = request.data.get("metas", [])
        metas_carteiras = request.data.get("carteiras", [])
        if not metas and not metas_carteiras:
            return Response({"error": "Nenhuma meta fornecida"}, status=status.HTTP_400_BAD_REQUEST)

        erros = []

        if metas:
            carteira = self._carteira_em_foco(request)
            if carteira is None:
                erros.append("Nenhuma carteira disponível para gravar as metas por ativo")
            else:
                for item in metas:
                    ativo_id = item.get("ativo", item.get("id"))
                    meta_val = item.get("meta")
                    if ativo_id is None or meta_val is None:
                        continue
                    atualizadas = PosicaoCarteira.objects.filter(
                        usuario=request.user, carteira=carteira, ativo_id=ativo_id
                    ).update(meta_porcentagem=Decimal(str(meta_val)))
                    if not atualizadas:
                        erros.append(
                            f"Ativo {ativo_id} não tem posição em {carteira.nome}"
                        )

        for item in metas_carteiras:
            carteira_id = item.get("id")
            meta_val = item.get("meta")
            if carteira_id is None or meta_val is None:
                continue
            atualizadas = Carteira.objects.filter(
                usuario=request.user, pk=carteira_id
            ).update(meta_porcentagem=Decimal(str(meta_val)))
            if not atualizadas:
                erros.append(f"Carteira com id {carteira_id} não encontrada")

        if erros:
            return Response({"status": "parcial", "errors": erros}, status=status.HTTP_207_MULTI_STATUS)

        return Response({"status": "sucesso"}, status=status.HTTP_200_OK)

    def _carteira_em_foco(self, request) -> Carteira | None:
        """Resolve a carteira cujo plano por ativo será montado.

        Returns:
            Carteira | None: A carteira explicitamente solicitada em `?carteira=`, ou None se consolidado.
        """
        carteiras = Carteira.objects.filter(usuario=request.user)
        carteira_id = carteira_do_request(request)
        if carteira_id:
            return carteiras.filter(pk=carteira_id).first()
        return None

    def _plano_entre_carteiras(self, usuario) -> list[dict]:
        """Compara o peso atual de cada carteira no patrimônio com a meta declarada.

        Returns:
            list[dict]: Uma entrada por carteira ativa, com valor atual, ideal e diferença.
        """
        carteiras = list(Carteira.objects.filter(usuario=usuario, ativa=True))
        valores = {
            linha["carteira_id"]: linha["total"] or Decimal(0)
            for linha in PosicaoCarteira.objects.filter(usuario=usuario)
            .values("carteira_id")
            .annotate(
                total=Sum(
                    F("quantidade") * F("preco_medio"),
                    output_field=DecimalField(max_digits=19, decimal_places=4),
                )
            )
        }
        total = sum(valores.values()) or Decimal(0)

        plano = []
        for carteira in carteiras:
            valor_atual = float(valores.get(carteira.id, Decimal(0)))
            meta = float(carteira.meta_porcentagem)
            valor_ideal = (meta / 100.0) * float(total)
            plano.append({
                "id": carteira.id,
                "nome": carteira.nome,
                "instituicao": carteira.instituicao,
                "cor": carteira.cor,
                "meta_porcentagem": meta,
                "valor_atual": valor_atual,
                "perc_atual": (valor_atual / float(total) * 100) if total > 0 else 0.0,
                "valor_ideal": valor_ideal,
                "diferenca": valor_ideal - valor_atual,
            })
        return plano



