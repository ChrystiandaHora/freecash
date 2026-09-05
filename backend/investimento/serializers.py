"""Serializadores do Django REST Framework para o Módulo de Investimentos.

Responsável por mapear e validar os payloads trafegados entre o cliente React
e a base de dados de ativos da bolsa, classes de investimento e ordens históricas.
"""

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from rest_framework import serializers
from .models import (
    ClasseAtivo,
    CategoriaAtivo,
    SubcategoriaAtivo,
    Ativo,
    Carteira,
    DetalheRendaFixa,
    PosicaoCarteira,
    Transacao,
    Cotacao,
)

DETALHE_RENDA_FIXA_FIELDS = ("data_vencimento", "emissor", "indexador", "taxa")


class CarteiraSerializer(serializers.ModelSerializer):
    """Serializador para o modelo Carteira (a custódia numa corretora ou banco)."""

    total_ativos = serializers.SerializerMethodField()
    pode_excluir = serializers.SerializerMethodField()
    valor_investido = serializers.SerializerMethodField()

    class Meta:
        model = Carteira
        fields = [
            'id', 'uuid', 'nome', 'instituicao', 'cor', 'meta_porcentagem',
            'considerar_no_saldo', 'ativa', 'ordem', 'total_ativos', 'valor_investido',
            'pode_excluir', 'criada_em', 'atualizada_em',
        ]
        read_only_fields = ['id', 'uuid', 'criada_em', 'atualizada_em']

    def get_total_ativos(self, obj) -> int:
        """Conta quantos ativos ainda têm posição aberta nesta carteira.

        Lê a anotação de `CarteiraViewSet.get_queryset` quando ela existe, e só cai na
        consulta própria fora da listagem — num `retrieve` ou em teste que instancie o
        serializer direto sobre o modelo.

        Returns:
            int: Ativos com quantidade maior que zero.
        """
        anotado = getattr(obj, "ativos_com_posicao", None)
        if anotado is not None:
            return anotado
        return obj.posicoes.filter(quantidade__gt=0).count()

    def get_valor_investido(self, obj) -> float:
        """Custo de aquisição do que está custodiado nesta carteira.

        É a resposta à pergunta principal da tela de Carteiras — "quanto tenho em cada
        corretora" —, que antes só mostrava a contagem de ativos. Usa custo, e não valor
        a mercado, porque o custo não depende de haver cotação do dia para cada papel.

        Returns:
            float: Soma de quantidade × preço médio das posições.
        """
        anotado = getattr(obj, "valor_investido", None)
        if anotado is None:
            anotado = obj.posicoes.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantidade") * F("preco_medio"),
                        output_field=DecimalField(max_digits=19, decimal_places=4),
                    )
                )
            )["total"] or Decimal(0)
        return float(anotado)

    def get_pode_excluir(self, obj) -> bool:
        """Indica se a carteira pode ser excluída — mesmo critério do `destroy`.

        Lê a anotação da view quando ela existe; sem isso, seria uma consulta por
        carteira na listagem.

        Returns:
            bool: True se não há transações registradas.
        """
        anotado = getattr(obj, "tem_transacoes", None)
        if anotado is not None:
            return not anotado
        return not obj.transacoes.exists()


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
            'quantidade', 'preco_medio', 'valor_total',
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
        """Injeta os campos de `DetalheRendaFixa` no payload plano de saída.

        Quando a requisição está filtrada por carteira, sobrescreve quantidade, preço
        médio e os derivados com os da posição naquela custódia. O formato do payload
        continua idêntico — a tela lê os mesmos campos, e o filtro muda o que eles
        significam, em vez de exigir um contrato novo do frontend.
        """
        rep = super().to_representation(instance)
        detalhe = getattr(instance, "detalhe_renda_fixa", None)
        for field in DETALHE_RENDA_FIXA_FIELDS:
            value = getattr(detalhe, field, None) if detalhe else None
            rep[field] = value.isoformat() if hasattr(value, "isoformat") else value

        posicao = self._posicao_filtrada(instance)
        if posicao is not None:
            cotacao = instance.cotacao_atual
            valor_investido = posicao.quantidade * posicao.preco_medio
            valor_atual = (
                posicao.quantidade * cotacao if cotacao is not None else valor_investido
            )
            rentabilidade = valor_atual - valor_investido
            rep['quantidade'] = str(posicao.quantidade)
            rep['preco_medio'] = str(posicao.preco_medio)
            rep['valor_total'] = str(valor_investido)
            rep['valor_total_atual'] = str(valor_atual)
            rep['rentabilidade'] = str(rentabilidade)
            rep['rentabilidade_percentual'] = str(
                (rentabilidade / valor_investido * 100) if valor_investido else 0
            )
            rep['carteira'] = posicao.carteira_id
            rep['meta_porcentagem'] = str(posicao.meta_porcentagem)
        else:
            # `null` no consolidado: omitir a chave fazia a soma virar zero em silêncio
            rep['carteira'] = None
            rep['meta_porcentagem'] = None
        return rep

    def _posicao_filtrada(self, instance):
        """Devolve a posição da carteira em foco, se a requisição pediu uma.

        Lê do `to_attr` preenchido pelo `Prefetch` da view, para não disparar uma
        consulta por ativo na listagem.

        Returns:
            PosicaoCarteira | None: A posição naquela custódia, ou None sem filtro.
        """
        if not self.context.get("carteira_id"):
            return None
        posicoes = getattr(instance, "posicao_filtrada", None)
        return posicoes[0] if posicoes else None

    def validate_ticker(self, value):
        """Recusa um ticker que o usuário já tem, explicando o caminho certo.

        O `unique_together ("usuario", "ticker")` do modelo não vira validador
        automático do DRF porque `usuario` não está entre os campos do serializer —
        ele é atribuído no `perform_create`. Sem esta checagem, a colisão chega ao
        banco como `IntegrityError` e sai como **500**, com uma mensagem opaca.

        A confusão ficou provável com as carteiras: querer o mesmo papel em duas
        corretoras leva naturalmente a cadastrá-lo de novo. Mas o ativo é único e a
        custódia vem da ordem, então a mensagem aponta para lá.
        """
        usuario = self.context['request'].user
        existentes = Ativo.objects.filter(usuario=usuario, ticker=value)
        if self.instance:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError(
                f"Você já tem {value} cadastrado. O ativo é um só, mesmo estando em "
                "mais de uma corretora — para tê-lo também em outra carteira, lance "
                "uma ordem de compra no Histórico escolhendo a carteira."
            )
        return value

    def validate_cnpj(self, value):
        if value:
            # Remove qualquer caractere não numérico
            clean_cnpj = "".join(filter(str.isdigit, value))
            if len(clean_cnpj) != 14:
                raise serializers.ValidationError("O CNPJ deve conter exatamente 14 dígitos numéricos.")
            return clean_cnpj
        return value

    def validate(self, attrs: dict) -> dict:
        """Sanitiza campos opcionais nulos de Renda Fixa/Variável.

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


class PosicaoCarteiraSerializer(serializers.ModelSerializer):
    """Serializador da posição de um ativo dentro de uma carteira.

    Aninha o ativo para que a tela consiga exibir ticker, nome e cotação sem uma
    segunda requisição, e a carteira para identificar a custódia.
    """
    ativo_detalhe = AtivoSerializer(source='ativo', read_only=True)
    carteira_detalhe = CarteiraSerializer(source='carteira', read_only=True)
    valor_investido = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    valor_total_atual = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)

    class Meta:
        model = PosicaoCarteira
        fields = [
            'id', 'uuid', 'carteira', 'carteira_detalhe', 'ativo', 'ativo_detalhe',
            'quantidade', 'custo_total', 'preco_medio', 'meta_porcentagem',
            'valor_investido', 'valor_total_atual', 'criada_em', 'atualizada_em',
        ]
        # Cache derivado das transações: gravável pela API seria sobrescrito no recálculo
        read_only_fields = [
            'id', 'uuid', 'carteira', 'ativo', 'quantidade', 'custo_total',
            'preco_medio', 'criada_em', 'atualizada_em',
        ]


class TransacaoInvestimentoSerializer(serializers.ModelSerializer):
    """Serializador para o modelo Transacao (registro de ordens).

    Serve dados completos de cotações, taxas e aninha detalhes do Ativo operado.
    """
    ativo_detalhe = AtivoSerializer(source='ativo', read_only=True)
    carteira_detalhe = CarteiraSerializer(source='carteira', read_only=True)

    class Meta:
        model = Transacao
        fields = [
            'id', 'uuid', 'ativo', 'ativo_detalhe', 'carteira', 'carteira_detalhe',
            'tipo', 'data', 'quantidade', 'preco_unitario', 'taxas', 'valor_total',
            'grupo_transferencia', 'criada_em', 'atualizada_em'
        ]
        read_only_fields = [
            'id', 'uuid', 'valor_total', 'grupo_transferencia',
            'criada_em', 'atualizada_em',
        ]

    def validate_carteira(self, value):
        """Impede apontar a ordem para a carteira de outro usuário.

        O `get_queryset` da view isola a leitura, mas o corpo do POST carrega um id
        arbitrário — sem esta checagem, uma ordem poderia ser gravada na custódia
        alheia.
        """
        usuario = self.context['request'].user
        if value.usuario_id != usuario.id:
            raise serializers.ValidationError("Carteira não encontrada.")
        return value

    def validate_tipo(self, value):
        """Barra a criação manual de pernas de transferência.

        Transferência entra pela ação `transferir/`, que grava as duas pernas juntas.
        Criar uma perna solta deixaria cotas duplicadas ou desaparecidas.
        """
        if value in Transacao.TIPOS_TRANSFERENCIA:
            raise serializers.ValidationError(
                "Transferências são registradas pelo endpoint de transferência."
            )
        return value

    def validate(self, attrs):
        """Impede a modificação de pernas de transferência."""
        if self.instance and self.instance.grupo_transferencia:
            raise serializers.ValidationError(
                "Transações de transferência não podem ser editadas diretamente. Exclua a transferência e realize-a novamente."
            )
        return super().validate(attrs)


class TransferenciaSerializer(serializers.Serializer):
    """Valida uma transferência de custódia entre duas carteiras do usuário.

    Não é um `ModelSerializer` porque a operação grava **duas** transações ligadas
    pelo mesmo `grupo_transferencia`, e não uma.
    """

    ativo = serializers.PrimaryKeyRelatedField(queryset=Ativo.objects.none())
    origem = serializers.PrimaryKeyRelatedField(queryset=Carteira.objects.none())
    destino = serializers.PrimaryKeyRelatedField(queryset=Carteira.objects.none())
    quantidade = serializers.DecimalField(max_digits=19, decimal_places=8, min_value=Decimal("0.00000001"))
    data = serializers.DateField(required=False)

    def __init__(self, *args, **kwargs):
        """Restringe os querysets ao usuário da requisição."""
        super().__init__(*args, **kwargs)
        usuario = self.context['request'].user
        self.fields['ativo'].queryset = Ativo.objects.filter(usuario=usuario)
        self.fields['origem'].queryset = Carteira.objects.filter(usuario=usuario)
        self.fields['destino'].queryset = Carteira.objects.filter(usuario=usuario)

    def validate(self, attrs: dict) -> dict:
        """Garante carteiras distintas e quantidade disponível na origem.

        Returns:
            dict: Atributos validados, acrescidos da posição de origem.
        """
        if attrs['origem'] == attrs['destino']:
            raise serializers.ValidationError(
                {"destino": "A carteira de destino deve ser diferente da de origem."}
            )

        posicao = PosicaoCarteira.objects.filter(
            carteira=attrs['origem'], ativo=attrs['ativo']
        ).first()
        disponivel = posicao.quantidade if posicao else Decimal(0)

        if attrs['quantidade'] > disponivel:
            raise serializers.ValidationError(
                {
                    "quantidade": (
                        f"A carteira de origem tem apenas {disponivel} "
                        f"de {attrs['ativo'].ticker}."
                    )
                }
            )

        attrs['posicao_origem'] = posicao
        return attrs

