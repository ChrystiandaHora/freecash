"""Serializadores do Django REST Framework para o Módulo de Investimentos.

Responsável por mapear e validar os payloads trafegados entre o cliente React
e a base de dados de ativos da bolsa, classes de investimento e ordens históricas.
"""

from rest_framework import serializers
from .models import ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo, Ativo, DetalheRendaFixa, Transacao, Cotacao

DETALHE_RENDA_FIXA_FIELDS = ("data_vencimento", "emissor", "indexador", "taxa")


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

    # Campos de Renda Fixa: não são mais atributos de `Ativo` (vivem em
    # `DetalheRendaFixa`, ligado 1:1). Declarados aqui como campos "soltos" para
    # manter o payload da API idêntico ao anterior — nenhuma mudança de contrato
    # para o frontend. Ver to_representation/create/update abaixo.
    data_vencimento = serializers.DateField(allow_null=True, required=False, write_only=True)
    emissor = serializers.CharField(allow_null=True, allow_blank=True, required=False, write_only=True)
    indexador = serializers.CharField(allow_null=True, allow_blank=True, required=False, write_only=True)
    taxa = serializers.DecimalField(max_digits=9, decimal_places=4, allow_null=True, required=False, write_only=True)
    cnpj = serializers.CharField(allow_null=True, allow_blank=True, required=False)

    historico_cotacoes = serializers.SerializerMethodField()

    class Meta:
        model = Ativo
        fields = [
            'id', 'uuid', 'ticker', 'nome', 'cnpj', 'subcategoria', 'subcategoria_detalhe',
            'data_vencimento', 'emissor', 'indexador', 'taxa', 'moeda', 'ativo',
            'meta_porcentagem', 'quantidade', 'preco_medio', 'valor_total',
            'cotacao_atual', 'valor_total_atual', 'rentabilidade', 'rentabilidade_percentual',
            'historico_cotacoes', 'criada_em', 'atualizada_em'
        ]
        read_only_fields = ['id', 'uuid', 'quantidade', 'preco_medio', 'criada_em', 'atualizada_em']

    def get_historico_cotacoes(self, obj) -> list[dict]:
        """Retorna a série histórica das últimas 30 cotações ordenadas cronologicamente."""
        recent_cotacoes = list(obj.cotacoes.all().order_by('-data')[:30])
        recent_cotacoes.reverse()
        return [
            {"data": str(c.data), "valor": float(c.valor)}
            for c in recent_cotacoes
        ]

    def to_representation(self, instance):
        """Injeta os campos de `DetalheRendaFixa` no payload plano de saída."""
        rep = super().to_representation(instance)
        detalhe = getattr(instance, "detalhe_renda_fixa", None)
        for field in DETALHE_RENDA_FIXA_FIELDS:
            value = getattr(detalhe, field, None) if detalhe else None
            rep[field] = value.isoformat() if hasattr(value, "isoformat") else value
        return rep

    def validate_cnpj(self, value):
        if value:
            # Remove qualquer caractere não numérico
            clean_cnpj = "".join(filter(str.isdigit, value))
            if len(clean_cnpj) != 14:
                raise serializers.ValidationError("O CNPJ deve conter exatamente 14 dígitos numéricos.")
            return clean_cnpj
        return value

    def validate(self, attrs) -> dict:
        """Sanitiza campos opcionais nulos de Renda Fixa/Variável.

        Args:
            attrs (dict): Atributos de entrada validados.

        Returns:
            dict: Atributos pós-sanitização.
        """
        if 'emissor' in attrs and attrs['emissor'] is None:
            attrs['emissor'] = ""
        if 'indexador' in attrs and attrs['indexador'] is None:
            attrs['indexador'] = ""
        if 'taxa' in attrs and attrs['taxa'] is None:
            attrs['taxa'] = 0
        return super().validate(attrs)

    def _extrair_detalhe_renda_fixa(self, validated_data) -> dict:
        """Remove e retorna os campos de renda fixa de `validated_data`."""
        return {
            field: validated_data.pop(field)
            for field in DETALHE_RENDA_FIXA_FIELDS
            if field in validated_data
        }

    def create(self, validated_data):
        detalhe_data = self._extrair_detalhe_renda_fixa(validated_data)
        ativo = super().create(validated_data)
        if any(detalhe_data.values()):
            DetalheRendaFixa.objects.create(ativo=ativo, **detalhe_data)
        return ativo

    def update(self, instance, validated_data):
        detalhe_data = self._extrair_detalhe_renda_fixa(validated_data)
        ativo = super().update(instance, validated_data)
        if detalhe_data:
            DetalheRendaFixa.objects.update_or_create(ativo=ativo, defaults=detalhe_data)
        return ativo


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

