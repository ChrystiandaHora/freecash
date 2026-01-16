from decimal import Decimal
from django.db.models import Sum, F
from investimento.models import Ativo, Transacao


def recalcular_ativo(ativo: Ativo):
    """
    Recalcula o preço médio e a quantidade atual de um ativo
    baseado em todo o histórico de transações.
    """
    transacoes = ativo.transacoes.order_by("data", "criada_em")

    quantidade_total = Decimal(0)
    custo_total = Decimal(0)

    for t in transacoes:
        qtd = t.quantidade
        valor = t.valor_total  # Já inclui taxas se a lógica de salvar estiver certa, mas vamos usar o bruto calculado aqui para garantir PM correto

        if t.tipo == Transacao.TIPO_COMPRA:
            # PM ponderado
            # Novo Custo = Custo Anterior + (Qtd * Preco) + Taxas
            # Mas PM fiscal geralmente inclui taxas. Vamos assumir valor_total como o custo de aquisição.
            custo_aquisicao = t.valor_total

            custo_total += custo_aquisicao
            quantidade_total += qtd

        elif t.tipo == Transacao.TIPO_VENDA:
            # Venda reduz quantidade, mas NÃO altera preço médio
            if quantidade_total > 0:
                # Proporção vendida
                preco_medio_atual = custo_total / quantidade_total

                # Custo abatido = Quantidade Vendida * Preço Médio Atual
                custo_abatido = qtd * preco_medio_atual

                custo_total -= custo_abatido
                quantidade_total -= qtd
            else:
                # Venda a descoberto ou erro de dados, zera ou mantem negativo
                quantidade_total -= qtd

        # Dividendos não alteram PM nem quantidade (são entradas de caixa)

    # Evita divisão por zero e arredondamentos estranhos
    if quantidade_total > 0:
        ativo.preco_medio = custo_total / quantidade_total
    else:
        ativo.preco_medio = Decimal(0)
        quantidade_total = Decimal(0)  # evita -0.000...

    ativo.quantidade = quantidade_total
    ativo.save(update_fields=["quantidade", "preco_medio"])
