"""Sinais e Gatilhos de Banco de Dados do Módulo de Investimentos.

Este módulo escuta e processa eventos do ciclo de vida dos modelos do Django (como criação de usuários
e inserção/deleção de transações), acionando automações como a inicialização da árvore hierárquica
de investimentos padrão e o recálculo automático de saldos e preços médios da carteira.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo, Transacao
from .calculators import recalcular_ativo
from django.db.models.signals import post_delete


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_classificacao_padrao(sender, instance, created, **kwargs):
    """Inicializa a estrutura padrão de classes, categorias e subcategorias de ativos para novos usuários.

    Executado logo após a criação de um novo usuário Django, garantindo que ele tenha uma árvore
    de decisão padrão populada (Renda Fixa, Renda Variável, Multimercado, Cambial, Criptoativos)
    para classificar seus investimentos na B3.

    Args:
        sender (Model): A classe do modelo que enviou o sinal (User).
        instance (User): A instância do usuário recém-criada.
        created (bool): Flag indicando se um novo registro foi criado.
        **kwargs: Parâmetros adicionais repassados pelo sinal.
    """
    if created:
        # 1. Renda Fixa
        rf = ClasseAtivo.objects.create(usuario=instance, nome="Renda Fixa")

        # 1.1 Indexado
        cat_idx = CategoriaAtivo.objects.create(
            usuario=instance, classe=rf, nome="Pós-fixado (Indexado)"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_idx, nome="Tesouro Selic"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_idx, nome="CDB/RDB"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_idx, nome="LCI/LCA"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance,
            categoria=cat_idx,
            nome="Crédito Privado (CRI/CRA/Debêntures)",
        )

        # 1.2 Inflação
        cat_ipca = CategoriaAtivo.objects.create(
            usuario=instance, classe=rf, nome="Inflação (IPCA)"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_ipca, nome="Tesouro IPCA+"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_ipca, nome="Debêntures Incentivadas"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_ipca, nome="Outros IPCA"
        )

        # 1.3 Pré-fixado
        cat_pre = CategoriaAtivo.objects.create(
            usuario=instance, classe=rf, nome="Pré-fixado"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_pre, nome="Tesouro Pré"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_pre, nome="CDB Pré"
        )

        # 2. Renda Variável
        rv = ClasseAtivo.objects.create(usuario=instance, nome="Renda Variável")

        # 2.1 Ações
        cat_acoes = CategoriaAtivo.objects.create(
            usuario=instance, classe=rv, nome="Ações"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_acoes, nome="Ações Brasil"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_acoes, nome="BDRs (Internacional)"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_acoes, nome="Small Caps"
        )

        # 2.2 FIIs
        cat_fii = CategoriaAtivo.objects.create(
            usuario=instance, classe=rv, nome="Fundos Imobiliários (FIIs)"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_fii, nome="FII de Tijolo"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_fii, nome="FII de Papel"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_fii, nome="FII Híbrido/Outros"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_fii, nome="Fiagro"
        )

        # 2.3 ETFs
        cat_etf = CategoriaAtivo.objects.create(
            usuario=instance, classe=rv, nome="ETFs"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_etf, nome="ETF Renda Variável"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_etf, nome="ETF Renda Fixa"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_etf, nome="ETF Cripto"
        )

        # 3. Multimercado
        mm = ClasseAtivo.objects.create(usuario=instance, nome="Multimercado")
        cat_mm_est = CategoriaAtivo.objects.create(
            usuario=instance, classe=mm, nome="Estratégia"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_mm_est, nome="Macro"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_mm_est, nome="Long & Short"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_mm_est, nome="Trading"
        )

        # 4. Cambial
        cambial = ClasseAtivo.objects.create(usuario=instance, nome="Cambial")
        cat_moeda = CategoriaAtivo.objects.create(
            usuario=instance, classe=cambial, nome="Moedas"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_moeda, nome="Dólar"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_moeda, nome="Euro"
        )

        # 5. Criptoativos
        cripto = ClasseAtivo.objects.create(usuario=instance, nome="Criptoativos")
        cat_coins = CategoriaAtivo.objects.create(
            usuario=instance, classe=cripto, nome="Moedas Digitais"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_coins, nome="Bitcoin"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_coins, nome="Ethereum"
        )
        SubcategoriaAtivo.objects.create(
            usuario=instance, categoria=cat_coins, nome="Altcoins"
        )


@receiver(post_save, sender=Transacao)
@receiver(post_delete, sender=Transacao)
def atualizar_ativo_apos_transacao(sender, instance, **kwargs):
    """Gatilha o recálculo de preço médio e quantidade em custódia de um ativo após transações.

    Escuta inserções, atualizações ou deleções de transações financeiras (compras/vendas),
    disparando a rotina matemática de PM fiscal ponderado para manter os dados de custódia
    atualizados.

    Args:
        sender (Model): A classe do modelo que enviou o sinal (Transacao).
        instance (Transacao): A instância da transação que sofreu a mutação.
        **kwargs: Parâmetros adicionais repassados pelo sinal.
    """
    if instance.ativo:
        recalcular_ativo(instance.ativo)

