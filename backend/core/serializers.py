"""
Serializadores do Django REST Framework para o Módulo Core.

Traduz e valida os payloads trafegados entre o cliente React e os modelos relacionais
PostgreSQL, aplicando lógica sob medida de cálculo de faturas de cartão de crédito
e formatação de datas de vencimento.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Categoria, Conta, CartaoCredito, ExtratoImportado, LinhaExtrato

class CategoriaSerializer(serializers.ModelSerializer):
    """Serializador do modelo Categoria do Django REST Framework.

    Responsável por serializar e desserializar registros de Categoria financeira,
    aplicando controle de apenas-leitura em metadados gerados pelo sistema.
    """
    class Meta:
        model = Categoria
        fields = ['id', 'uuid', 'nome', 'tipo', 'is_default', 'criada_em', 'atualizada_em']
        read_only_fields = ['id', 'uuid', 'is_default', 'criada_em', 'atualizada_em']


class CartaoCreditoSerializer(serializers.ModelSerializer):
    """Serializador padrão do modelo CartaoCredito.

    Garante o mapeamento dos campos básicos do cartão, como limite, dia de
    fechamento, vencimento de faturas e integridade dos UUIDs.
    """
    class Meta:
        model = CartaoCredito
        fields = [
            'id', 'uuid', 'nome', 'bandeira', 'ultimos_digitos', 
            'limite', 'dia_fechamento', 'dia_vencimento', 'ativo', 
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']


class ContaSerializer(serializers.ModelSerializer):
    """Serializador padrão do modelo Conta.

    Fornece aninhamento profundo opcional para categorias e cartões de crédito,
    além de calcular dinamicamente o status de atraso de lançamentos financeiros.
    """
    categoria_detalhe = CategoriaSerializer(source='categoria', read_only=True)
    cartao_detalhe = CartaoCreditoSerializer(source='cartao', read_only=True)
    esta_atrasada = serializers.BooleanField(read_only=True)

    class Meta:
        model = Conta
        fields = [
            'id', 'uuid', 'tipo', 'descricao', 'valor', 'data_prevista',
            'transacao_realizada', 'data_realizacao', 'categoria', 
            'categoria_detalhe', 'cartao', 'cartao_detalhe', 
            'data_compra', 'eh_fatura_cartao', 'esta_atrasada',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'esta_atrasada', 'criada_em', 'atualizada_em']


class ExtratoImportadoSerializer(serializers.ModelSerializer):
    """Serializador do lote ExtratoImportado.

    Agrega o detalhamento da contagem de linhas e metadados sobre o progresso
    do processamento de conciliação.
    """
    banco_display = serializers.CharField(source='get_banco_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    cartao_detalhe = CartaoCreditoSerializer(source='cartao', read_only=True)
    linhas_pendentes = serializers.SerializerMethodField()

    class Meta:
        model = ExtratoImportado
        fields = [
            'id', 'uuid', 'arquivo_nome', 'banco', 'banco_display',
            'status', 'status_display', 'linhas_encontradas', 'linhas_importadas',
            'erro_mensagem', 'cartao', 'cartao_detalhe', 'linhas_pendentes',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']

    def get_linhas_pendentes(self, obj) -> int:
        """Calcula o número de linhas de extrato que continuam pendentes de conciliação.

        Args:
            obj (ExtratoImportado): A instância do extrato importado.

        Returns:
            int: Quantidade de linhas pendentes.
        """
        return obj.linhas.filter(status='pendente').count()


class LinhaExtratoSerializer(serializers.ModelSerializer):
    """Serializador do modelo LinhaExtrato.

    Fornece a representação serializada das linhas brutas lidas dos arquivos OFX,
    mapeando as contas vinculadas após a conciliação do usuário.
    """
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    conta_vinculada_detalhe = ContaSerializer(source='conta_vinculada', read_only=True)

    class Meta:
        model = LinhaExtrato
        fields = [
            'id', 'uuid', 'extrato', 'data', 'descricao', 'valor',
            'tipo', 'tipo_display', 'status', 'status_display',
            'conta_vinculada', 'conta_vinculada_detalhe',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']


class CartaoCreditoAPISerializer(serializers.ModelSerializer):
    """Serializador otimizado sob medida para a tela de cartões do React.

    Injeta estatísticas agregadas de faturas abertas, histórico de compras recentes
    e campos dinâmicos de expiração do cartão de crédito.
    """
    fatura_atual = serializers.SerializerMethodField()
    compras_recentes = serializers.SerializerMethodField()
    final = serializers.CharField(source='ultimos_digitos', read_only=True)
    banco = serializers.CharField(source='nome', read_only=True)
    titular = serializers.SerializerMethodField()
    validade = serializers.SerializerMethodField()

    class Meta:
        model = CartaoCredito
        fields = [
            'id', 'uuid', 'nome', 'bandeira', 'final', 'banco',
            'limite', 'dia_fechamento', 'dia_vencimento', 'ativo',
            'fatura_atual', 'compras_recentes', 'titular', 'validade',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']

    def get_fatura_atual(self, obj) -> float:
        """Soma o valor total das despesas não pagas e não faturadas deste cartão.

        Args:
            obj (CartaoCredito): Instância do cartão analisado.

        Returns:
            float: O valor acumulado da fatura em aberto.
        """
        from django.db.models import Sum
        usuario = self.context['request'].user
        # Fatura atual = sum of unpaid despesas (eh_fatura_cartao=False) on this card
        total = Conta.objects.filter(
            usuario=usuario,
            cartao=obj,
            eh_fatura_cartao=False,
            transacao_realizada=False
        ).aggregate(total=Sum('valor'))['total']
        return float(total) if total else 0.0

    def get_compras_recentes(self, obj) -> list[dict]:
        """Obtém as últimas 8 compras individuais efetuadas neste cartão de crédito.

        Args:
            obj (CartaoCredito): Instância do cartão analisado.

        Returns:
            list[dict]: Lista de dicionários contendo dados simplificados das compras.
        """
        usuario = self.context['request'].user
        # Last 8 purchases on this card
        purchases = Conta.objects.filter(
            usuario=usuario,
            cartao=obj,
            eh_fatura_cartao=False
        ).select_related('categoria').order_by('-data_compra', '-id')[:8]
        
        compras_recentes = []
        for p in purchases:
            compras_recentes.append({
                'id': p.id,
                'descricao': p.descricao,
                'data': p.data_compra.strftime('%Y-%m-%d') if p.data_compra else p.data_prevista.strftime('%Y-%m-%d'),
                'valor': float(p.valor),
                'categoria': p.categoria.nome if p.categoria else 'default'
            })
        return compras_recentes

    def get_titular(self, obj) -> str:
        """Retorna o nome do titular do cartão (nome do usuário autenticado).

        Args:
            obj (CartaoCredito): Instância do cartão analisado.

        Returns:
            str: Nome completo do usuário ou seu username.
        """
        user = self.context['request'].user
        return user.get_full_name() or user.username

    def get_validade(self, obj) -> str:
        """Gera uma string de validade dinâmica simulada no formato MM/AA.

        Args:
            obj (CartaoCredito): Instância do cartão analisado.

        Returns:
            str: Data de validade fictícia para renderização visual.
        """
        from django.utils import timezone
        target_year = (timezone.now().year + 4) % 100
        return f"12/{target_year:02d}"


class ContasPagarAPISerializer(serializers.ModelSerializer):
    """Serializador customizado otimizado para a exibição de Despesas (Contas a Pagar).

    Mapeia os campos relacionais de categoria e vencimento para propriedades de
    interface amigáveis.
    """
    categoria = serializers.CharField(source='categoria.nome', read_only=True)
    pago = serializers.BooleanField(source='transacao_realizada', read_only=True)
    data_vencimento = serializers.DateField(source='data_prevista', read_only=True)

    class Meta:
        model = Conta
        fields = [
            'id', 'uuid', 'tipo', 'descricao', 'valor', 'data_vencimento',
            'pago', 'data_realizacao', 'categoria', 'cartao',
            'data_compra', 'eh_fatura_cartao', 'esta_atrasada',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'esta_atrasada', 'criada_em', 'atualizada_em']


class ReceitasAPISerializer(serializers.ModelSerializer):
    """Serializador customizado otimizado para a exibição de Receitas.

    Facilita a visualização do estado de liquidação e recebimento.
    """
    categoria = serializers.CharField(source='categoria.nome', read_only=True)
    realizada = serializers.BooleanField(source='transacao_realizada', read_only=True)
    data_recebimento = serializers.DateField(source='data_prevista', read_only=True)

    class Meta:
        model = Conta
        fields = [
            'id', 'uuid', 'tipo', 'descricao', 'valor', 'data_recebimento',
            'realizada', 'data_realizacao', 'categoria', 'cartao',
            'eh_fatura_cartao', 'esta_atrasada',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'esta_atrasada', 'criada_em', 'atualizada_em']


class TransacaoAPISerializer(serializers.ModelSerializer):
    """Serializador unificado de transações para o extrato geral.

    Combina despesas e receitas sob termos genéricos de 'entrada' e 'saida',
    calculando a data da transação com base no fluxo de caixa real ou competência.
    """
    categoria = serializers.CharField(source='categoria.nome', read_only=True)
    tipo = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    class Meta:
        model = Conta
        fields = [
            'id', 'uuid', 'tipo', 'descricao', 'valor', 'data',
            'transacao_realizada', 'data_realizacao', 'categoria', 'cartao',
            'eh_fatura_cartao', 'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']

    def get_tipo(self, obj) -> str:
        """Determina a direção da transação financeira ('entrada' ou 'saida').

        Args:
            obj (Conta): Instância da conta analisada.

        Returns:
            str: Direção da transação.
        """
        return 'entrada' if obj.tipo == Conta.TIPO_RECEITA else 'saida'

    def get_data(self, obj) -> str:
        """Calcula a data final de transação no formato ISO de forma segura.

        Args:
            obj (Conta): Instância da conta analisada.

        Returns:
            str: Data da transação em formato ISO 8601.
        """
        data_val = getattr(obj, 'data_transacao', None)
        if data_val is None:
            data_val = obj.data_realizacao if obj.transacao_realizada and obj.data_realizacao else obj.data_prevista
        return data_val.isoformat() if data_val else None


class ComprasCartaoAPISerializer(serializers.ModelSerializer):
    """Serializador para compras individuais de cartão de crédito.

    Expõe dados ricos para a tela de 'Compras Cartão', incluindo detalhes
    do cartão e da categoria, e a data de vencimento calculada automaticamente.
    """
    cartao_detalhe = serializers.SerializerMethodField()
    categoria_detalhe = serializers.SerializerMethodField()
    data_vencimento = serializers.DateField(source='data_prevista', read_only=True)
    pago = serializers.BooleanField(source='transacao_realizada', read_only=True)

    class Meta:
        model = Conta
        fields = [
            'id', 'uuid', 'descricao', 'valor',
            'data_compra', 'data_vencimento',
            'pago', 'data_realizacao',
            'cartao', 'cartao_detalhe',
            'categoria', 'categoria_detalhe',
            'eh_fatura_cartao', 'esta_atrasada',
            'criada_em', 'atualizada_em',
        ]
        read_only_fields = ['id', 'uuid', 'esta_atrasada', 'criada_em', 'atualizada_em']

    def get_cartao_detalhe(self, obj) -> dict | None:
        """Retorna os dados resumidos do cartão associado à compra.

        Args:
            obj (Conta): Instância da compra.

        Returns:
            dict | None: Dados básicos do cartão ou None se não houver cartão.
        """
        if not obj.cartao:
            return None
        c = obj.cartao
        return {
            'id': c.id,
            'uuid': str(c.uuid),
            'nome': c.nome,
            'bandeira': c.bandeira,
            'final': c.ultimos_digitos,
        }

    def get_categoria_detalhe(self, obj) -> dict | None:
        """Retorna os dados resumidos da categoria associada à compra.

        Args:
            obj (Conta): Instância da compra.

        Returns:
            dict | None: Dados básicos da categoria ou None se não houver categoria.
        """
        if not obj.categoria:
            return None
        return {
            'id': obj.categoria.id,
            'nome': obj.categoria.nome,
            'tipo': obj.categoria.tipo,
        }


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    """Serializador JWT customizado para incluir informações básicas do usuário no token payload.

    Adiciona o username como claim customizada no token de acesso decodificável pelo frontend.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Injetar username no payload do token JWT
        token['username'] = user.username
        return token

