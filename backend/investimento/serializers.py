"""Serializadores do Django REST Framework para o Módulo de Investimentos.

Responsável por mapear e validar os payloads trafegados entre o cliente React
e a base de dados de ativos da bolsa, classes de investimento e ordens históricas.
"""

from rest_framework import serializers
from .models import ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo, Ativo, Transacao, Cotacao


class ClasseAtivoSerializer(serializers.ModelSerializer):
    """Serializador para o modelo ClasseAtivo.

    Trata os dados de macro classes financeiras de ativos (ex: Renda Fixa).
    """
    class Meta:
        model = ClasseAtivo
        fields = ['id', 'uuid', 'nome', 'ativa', 'criada_em', 'atualizada_em']
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']


class CategoriaAtivoSerializer(serializers.ModelSerializer):
    """Serializador para o modelo CategoriaAtivo.

    Inclui representação aninhada profunda da macro classe associada.
    """
    classe_detalhe = ClasseAtivoSerializer(source='classe', read_only=True)

    class Meta:
        model = CategoriaAtivo
        fields = ['id', 'uuid', 'classe', 'classe_detalhe', 'nome', 'ativa', 'criada_em', 'atualizada_em']
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']


class SubcategoriaAtivoSerializer(serializers.ModelSerializer):
    """Serializador para o modelo SubcategoriaAtivo.

    Aninha o detalhamento completo de sua categoria intermediária correspondente.
    """
    categoria_detalhe = CategoriaAtivoSerializer(source='categoria', read_only=True)

    class Meta:
        model = SubcategoriaAtivo
        fields = ['id', 'uuid', 'categoria', 'categoria_detalhe', 'nome', 'ativa', 'criada_em', 'atualizada_em']
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']


class AtivoSerializer(serializers.ModelSerializer):
    """Serializador consolidado de Ativos.

    Expõe propriedades calculadas e cacheadas sob demanda como valor total investido,
    cotações a mercado atualizadas, rentabilidade absoluta e percentual acumuladas.
    """
    subcategoria_detalhe = SubcategoriaAtivoSerializer(source='subcategoria', read_only=True)
    valor_total = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    cotacao_atual = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    valor_total_atual = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    rentabilidade = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    rentabilidade_percentual = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)

    emissor = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    indexador = serializers.CharField(allow_null=True, allow_blank=True, required=False)

    historico_cotacoes = serializers.SerializerMethodField()

    class Meta:
        model = Ativo
        fields = [
            'id', 'uuid', 'ticker', 'nome', 'subcategoria', 'subcategoria_detalhe',
            'data_vencimento', 'emissor', 'indexador', 'taxa', 'moeda', 'ativo', 
            'meta_porcentagem', 'quantidade', 'preco_medio', 'valor_total',
            'cotacao_atual', 'valor_total_atual', 'rentabilidade', 'rentabilidade_percentual',
            'historico_cotacoes', 'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'quantidade', 'preco_medio', 'criada_em', 'atualizada_em']

    def get_historico_cotacoes(self, obj) -> list[dict]:
        """Retorna a série histórica das últimas 30 cotações ordenadas cronologicamente."""
        return [
            {"data": str(c.data), "valor": float(c.valor)}
            for c in obj.cotacoes.all().order_by('data')[:30]
        ]

    def validate(self, attrs) -> dict:
        """Sanitiza campos opcionais nulos de Renda Fixa convertendo-os em strings vazias.

        Args:
            attrs (dict): Atributos de entrada validados.

        Returns:
            dict: Atributos pós-sanitização.
        """
        if 'emissor' in attrs and attrs['emissor'] is None:
            attrs['emissor'] = ""
        if 'indexador' in attrs and attrs['indexador'] is None:
            attrs['indexador'] = ""
        return super().validate(attrs)


class TransacaoInvestimentoSerializer(serializers.ModelSerializer):
    """Serializador para o modelo Transacao (registro de ordens).

    Serve dados completos de cotações, taxas e aninha detalhes do Ativo operado.
    """
    ativo_detalhe = AtivoSerializer(source='ativo', read_only=True)

    class Meta:
        model = Transacao
        fields = [
            'id', 'uuid', 'ativo', 'ativo_detalhe', 'tipo', 'data', 
            'quantidade', 'preco_unitario', 'taxas', 'valor_total',
            'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'valor_total', 'criada_em', 'atualizada_em']

