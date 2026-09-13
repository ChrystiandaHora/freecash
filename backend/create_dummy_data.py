"""
Script para criação de usuário de teste com dados realistas e balanceados.

Métricas simuladas conforme requisitos:
- Receitas mensais: ~ R$ 20.000,00 (R$ 20.080,00)
- Gastos mensais: ~ R$ 14.000,00 (R$ 14.000,00)
- Investimentos total aportado: R$ 168.000,00 distribuído exatamente em 20% (R$ 33.600,00) em cada classe de ativo:
  1. Renda Fixa (20%)
  2. Ações Brasil (20%)
  3. Fundos Imobiliários (FIIs) (20%)
  4. Internacional / BDRs (20%)
  5. Criptoativos (20%)
"""

import os
import django
from decimal import Decimal
from datetime import date, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freecash.settings")
django.setup()

from django.contrib.auth import get_user_model
from core.models import Categoria, Conta, CartaoCredito
from investimento.models import (
    ClasseAtivo,
    CategoriaAtivo,
    SubcategoriaAtivo,
    Ativo,
    Carteira,
    DetalheRendaFixa,
    Cotacao,
    PosicaoCarteira,
    Transacao,
)
from investimento.signals import criar_classificacao_padrao

User = get_user_model()

def seed_user_data(user):
    print(f"Populando dados realistas para o usuário '{user.username}'...")

    # Garante árvore hierárquica padrão se não existir
    if not user.classes_ativos.exists():
        criar_classificacao_padrao(sender=User, instance=user, created=True)

    # Limpa dados anteriores do usuário para um estado limpo
    Conta.objects.filter(usuario=user).delete()
    CartaoCredito.objects.filter(usuario=user).delete()
    Transacao.objects.filter(usuario=user).delete()
    Ativo.objects.filter(usuario=user).delete()

    today = date.today()
    current_year = today.year
    current_month = today.month

    # 1. Categorias Core
    cat_rec_salario, _ = Categoria.objects.get_or_create(usuario=user, nome="Salário & Pró-Labore", defaults={"tipo": "R"})
    cat_rec_consultoria, _ = Categoria.objects.get_or_create(usuario=user, nome="Consultoria & Serviços PJ", defaults={"tipo": "R"})
    cat_rec_proventos, _ = Categoria.objects.get_or_create(usuario=user, nome="Rendimentos & Dividendos", defaults={"tipo": "R"})

    cat_desp_moradia, _ = Categoria.objects.get_or_create(usuario=user, nome="Moradia & Aluguel", defaults={"tipo": "D"})
    cat_desp_veiculo, _ = Categoria.objects.get_or_create(usuario=user, nome="Transporte & Veículo", defaults={"tipo": "D"})
    cat_desp_cartao, _ = Categoria.objects.get_or_create(usuario=user, nome="Fatura Cartão de Crédito", defaults={"tipo": "D"})
    cat_desp_alimentacao, _ = Categoria.objects.get_or_create(usuario=user, nome="Supermercado & Alimentação", defaults={"tipo": "D"})
    cat_desp_saude, _ = Categoria.objects.get_or_create(usuario=user, nome="Saúde & Seguros", defaults={"tipo": "D"})
    cat_desp_utilidades, _ = Categoria.objects.get_or_create(usuario=user, nome="Utilidades & Contas Básicas", defaults={"tipo": "D"})
    cat_desp_lazer, _ = Categoria.objects.get_or_create(usuario=user, nome="Lazer & Assinaturas", defaults={"tipo": "D"})

    # 2. Cartões de Crédito (Nomes genéricos)
    c_platinum = CartaoCredito.objects.create(
        usuario=user,
        nome="Cartão Platinum Prime",
        limite=Decimal("35000.00"),
        dia_fechamento=15,
        dia_vencimento=25,
        ativo=True,
    )
    c_black = CartaoCredito.objects.create(
        usuario=user,
        nome="Cartão Black Executivo",
        limite=Decimal("45000.00"),
        dia_fechamento=25,
        dia_vencimento=5,
        ativo=True,
    )

    # 3. Receitas (~ R$ 20.000,00 -> Total R$ 20.080,00)
    d_salario = date(current_year, current_month, 5)
    d_consult = date(current_year, current_month, 12)
    d_provent = date(current_year, current_month, 15)

    Conta.objects.create(
        usuario=user,
        tipo="R",
        descricao="Salário & Remuneração Mensal",
        valor=Decimal("14500.00"),
        data_prevista=d_salario,
        transacao_realizada=True,
        data_realizacao=d_salario,
        categoria=cat_rec_salario,
    )
    Conta.objects.create(
        usuario=user,
        tipo="R",
        descricao="Consultoria Especializada PJ",
        valor=Decimal("4300.00"),
        data_prevista=d_consult,
        transacao_realizada=True,
        data_realizacao=d_consult,
        categoria=cat_rec_consultoria,
    )
    Conta.objects.create(
        usuario=user,
        tipo="R",
        descricao="Rendimentos FIIs & Dividendos Ações",
        valor=Decimal("1280.00"),
        data_prevista=d_provent,
        transacao_realizada=True,
        data_realizacao=d_provent,
        categoria=cat_rec_proventos,
    )

    # 4. Despesas (~ R$ 14.000,00 -> Total R$ 14.000,00)
    dt_black = date(current_year, current_month, 5)
    dt_saude = date(current_year, current_month, 8)
    dt_moradia = date(current_year, current_month, 10)
    dt_veiculo = date(current_year, current_month, 14)
    dt_mercado = date(current_year, current_month, 18)
    dt_assinat = date(current_year, current_month, 20)
    dt_platinum = date(current_year, current_month, 25)

    # Contas Pagas (Totalizando R$ 10.580,00 já liquidadas)
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Aluguel & Condomínio Residencial",
        valor=Decimal("4200.00"),
        data_prevista=dt_moradia,
        transacao_realizada=True,
        data_realizacao=dt_moradia,
        categoria=cat_desp_moradia,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Fatura Cartão Black Executivo",
        valor=Decimal("2400.00"),
        data_prevista=dt_black,
        transacao_realizada=True,
        data_realizacao=dt_black,
        categoria=cat_desp_cartao,
        cartao=c_black,
        eh_fatura_cartao=True,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Financiamento Parcela Veículo",
        valor=Decimal("1850.00"),
        data_prevista=dt_veiculo,
        transacao_realizada=True,
        data_realizacao=dt_veiculo,
        categoria=cat_desp_veiculo,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Supermercado Mensal & Hortifruti",
        valor=Decimal("1450.00"),
        data_prevista=dt_mercado,
        transacao_realizada=True,
        data_realizacao=dt_mercado,
        categoria=cat_desp_alimentacao,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Plano de Saúde Familiar Executivo",
        valor=Decimal("680.00"),
        data_prevista=dt_saude,
        transacao_realizada=True,
        data_realizacao=dt_saude,
        categoria=cat_desp_saude,
    )

    # Contas Pendentes do Mês (Totalizando R$ 3.420,00 a vencer)
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Fatura Cartão Platinum Prime",
        valor=Decimal("3100.00"),
        data_prevista=dt_platinum,
        transacao_realizada=False,
        categoria=cat_desp_cartao,
        cartao=c_platinum,
        eh_fatura_cartao=True,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Assinaturas de Software & Streaming",
        valor=Decimal("320.00"),
        data_prevista=dt_assinat,
        transacao_realizada=False,
        categoria=cat_desp_lazer,
    )

    # Contas extras para enriquecer as colunas do Kanban (Vence Hoje e Atrasada)
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Internet Fibra Óptica 1Gbps",
        valor=Decimal("190.00"),
        data_prevista=today,
        transacao_realizada=False,
        categoria=cat_desp_utilidades,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Energia Elétrica Concessionária",
        valor=Decimal("240.00"),
        data_prevista=today - timedelta(days=2),
        transacao_realizada=False,
        categoria=cat_desp_utilidades,
    )

    # 5. Compras no Cartão de Crédito
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Jantar Restaurante Empório",
        valor=Decimal("380.00"),
        data_prevista=dt_platinum,
        data_compra=today - timedelta(days=3),
        categoria=cat_desp_alimentacao,
        cartao=c_platinum,
        eh_fatura_cartao=False,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Passagens Aéreas Férias",
        valor=Decimal("1850.00"),
        data_prevista=dt_platinum,
        data_compra=today - timedelta(days=7),
        categoria=cat_desp_lazer,
        cartao=c_platinum,
        eh_fatura_cartao=False,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Manutenção Preventiva Carro",
        valor=Decimal("870.00"),
        data_prevista=dt_platinum,
        data_compra=today - timedelta(days=10),
        categoria=cat_desp_veiculo,
        cartao=c_platinum,
        eh_fatura_cartao=False,
    )

    # 6. INVESTIMENTOS (Total Aportado: R$ 168.000,00)
    # Exatamente 20% em cada uma das 5 classes (R$ 33.600,00 por classe):
    # 1. Renda Fixa: R$ 33.600,00 (20%)
    # 2. Ações Brasil: R$ 33.600,00 (20%)
    # 3. Fundos Imobiliários: R$ 33.600,00 (20%)
    # 4. Internacional (BDRs/ETFs): R$ 33.600,00 (20%)
    # 5. Criptoativos: R$ 33.600,00 (20%)

    sub_rf = SubcategoriaAtivo.objects.filter(usuario=user, categoria__classe__nome__icontains="Renda Fixa").first()
    sub_acoes = SubcategoriaAtivo.objects.filter(usuario=user, categoria__classe__nome__icontains="Renda Variável", nome__icontains="Ações").first()
    sub_fii = SubcategoriaAtivo.objects.filter(usuario=user, categoria__classe__nome__icontains="Renda Variável", nome__icontains="FII").first()
    sub_inter = (
        SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="BDR").first()
        or SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="Internacional").first()
        or SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="ETF").first()
    )
    sub_cripto = SubcategoriaAtivo.objects.filter(usuario=user, categoria__classe__nome__icontains="Cripto").first()

    # Fallbacks defensivos se alguma subcategoria não for localizada pelo filtro
    todas_subs = list(SubcategoriaAtivo.objects.filter(usuario=user))
    if not sub_rf: sub_rf = todas_subs[0]
    if not sub_acoes: sub_acoes = todas_subs[1] if len(todas_subs) > 1 else todas_subs[0]
    if not sub_fii: sub_fii = todas_subs[2] if len(todas_subs) > 2 else todas_subs[0]
    if not sub_inter: sub_inter = todas_subs[3] if len(todas_subs) > 3 else todas_subs[0]
    if not sub_cripto: sub_cripto = todas_subs[4] if len(todas_subs) > 4 else todas_subs[0]

    carteira_xp = Carteira.padrao_de(user)
    carteira_xp.nome = "Custódia Alpha Capital"
    carteira_xp.instituicao = "Alpha"
    carteira_xp.cor = "#0F0F0F"
    carteira_xp.meta_porcentagem = Decimal("60.00")
    carteira_xp.save()

    carteira_inter, _ = Carteira.objects.get_or_create(
        usuario=user,
        nome="Banco Digital Horizon",
        defaults={
            "instituicao": "Horizon",
            "cor": "#FF7A00",
            "meta_porcentagem": Decimal("40.00"),
            "considerar_no_saldo": True,
            "ordem": 1,
        },
    )

    # Definição dos ativos para somar exatamente R$ 168.000,00 aportados (20% por classe = R$ 33.600)
    assets_def = [
        # Classe 1: Renda Fixa (Total aportado = R$ 33.600,00)
        {
            "ticker": "SELIC2029",
            "nome": "Tesouro Selic 2029",
            "sub": sub_rf,
            "qtd": Decimal("2.24"),
            "pm": Decimal("15000.00"),
            "cot": Decimal("15450.00"),
            "meta": Decimal("20.00"),
            "carteira": "inter",
        },
        # Classe 2: Ações Brasil (15.000 + 12.600 + 6.000 = R$ 33.600,00)
        {
            "ticker": "VALE3",
            "nome": "Vale S.A.",
            "sub": sub_acoes,
            "qtd": Decimal("250"),
            "pm": Decimal("60.00"),
            "cot": Decimal("63.80"),
            "meta": Decimal("9.00"),
            "carteira": "xp",
        },
        {
            "ticker": "ITUB4",
            "nome": "Itaú Unibanco Holding S.A.",
            "sub": sub_acoes,
            "qtd": Decimal("400"),
            "pm": Decimal("31.50"),
            "cot": Decimal("34.25"),
            "meta": Decimal("7.50"),
            "carteira": "xp",
        },
        {
            "ticker": "WEGE3",
            "nome": "WEG S.A.",
            "sub": sub_acoes,
            "qtd": Decimal("150"),
            "pm": Decimal("40.00"),
            "cot": Decimal("43.40"),
            "meta": Decimal("3.50"),
            "carteira": "xp",
        },
        # Classe 3: FIIs (16.000 + 12.000 + 5.600 = R$ 33.600,00)
        {
            "ticker": "HGLG11",
            "nome": "CSHG Logística FII",
            "sub": sub_fii,
            "qtd": Decimal("100"),
            "pm": Decimal("160.00"),
            "cot": Decimal("166.20"),
            "meta": Decimal("10.00"),
            "carteira": "xp",
        },
        {
            "ticker": "KNCR11",
            "nome": "Kinea Rendimentos Imobiliários FII",
            "sub": sub_fii,
            "qtd": Decimal("120"),
            "pm": Decimal("100.00"),
            "cot": Decimal("103.50"),
            "meta": Decimal("7.00"),
            "carteira": "xp",
        },
        {
            "ticker": "MXRF11",
            "nome": "Maxi Renda FII",
            "sub": sub_fii,
            "qtd": Decimal("560"),
            "pm": Decimal("10.00"),
            "cot": Decimal("10.48"),
            "meta": Decimal("3.00"),
            "carteira": "xp",
        },
        # Classe 4: Internacional / BDRs / ETFs (21.600 + 12.000 = R$ 33.600,00)
        {
            "ticker": "IVVB11",
            "nome": "iShares S&P 500 Fundo de Índice",
            "sub": sub_inter,
            "qtd": Decimal("60"),
            "pm": Decimal("360.00"),
            "cot": Decimal("385.00"),
            "meta": Decimal("13.00"),
            "carteira": "xp",
        },
        {
            "ticker": "AAPL34",
            "nome": "Apple Inc. BDR",
            "sub": sub_inter,
            "qtd": Decimal("200"),
            "pm": Decimal("60.00"),
            "cot": Decimal("65.10"),
            "meta": Decimal("7.00"),
            "carteira": "xp",
        },
        # Classe 5: Criptoativos (25.600 + 8.000 = R$ 33.600,00)
        {
            "ticker": "BTC",
            "nome": "Bitcoin (BTC)",
            "sub": sub_cripto,
            "qtd": Decimal("0.08"),
            "pm": Decimal("320000.00"),
            "cot": Decimal("352000.00"),
            "meta": Decimal("15.00"),
            "carteira": "xp",
        },
        {
            "ticker": "ETH",
            "nome": "Ethereum (ETH)",
            "sub": sub_cripto,
            "qtd": Decimal("0.50"),
            "pm": Decimal("16000.00"),
            "cot": Decimal("18200.00"),
            "meta": Decimal("5.00"),
            "carteira": "xp",
        },
    ]

    for item in assets_def:
        carteira = carteira_xp if item["carteira"] == "xp" else carteira_inter
        ativo = Ativo.objects.create(
            usuario=user,
            ticker=item["ticker"],
            nome=item["nome"],
            subcategoria=item["sub"],
            quantidade=item["qtd"],
            preco_medio=item["pm"],
        )

        # Cotação a mercado
        Cotacao.objects.create(
            ativo=ativo,
            data=today,
            valor=item["cot"],
        )

        # Ordem de compra inicial realizada há 90 dias
        Transacao.objects.create(
            usuario=user,
            ativo=ativo,
            carteira=carteira,
            tipo="C",
            data=today - timedelta(days=90),
            quantidade=item["qtd"],
            preco_unitario=item["pm"],
            valor_total=item["qtd"] * item["pm"],
        )

        # Transações de proventos nos últimos 6 meses (Efeito Bola de Neve crescente)
        if item["ticker"] in ["HGLG11", "KNCR11", "MXRF11", "ITUB4", "VALE3"]:
            unit_val = Decimal("1.25") if "11" in item["ticker"] else Decimal("0.65")
            for m_offset in range(5, -1, -1):
                dt_div = today - timedelta(days=m_offset * 30 + 10)
                # Crescimento sutil simulando reinvestimento
                growth_factor = Decimal(str(1.0 + (5 - m_offset) * 0.05))
                Transacao.objects.create(
                    usuario=user,
                    ativo=ativo,
                    carteira=carteira,
                    tipo="D",
                    data=dt_div,
                    quantidade=item["qtd"],
                    preco_unitario=unit_val * growth_factor,
                    valor_total=(item["qtd"] * unit_val * growth_factor).quantize(Decimal("0.01")),
                )

        # Atualiza a meta percentual na posição da carteira
        PosicaoCarteira.objects.filter(carteira=carteira, ativo=ativo).update(
            meta_porcentagem=item["meta"]
        )

        if "SELIC" in item["ticker"]:
            DetalheRendaFixa.objects.create(
                ativo=ativo,
                emissor="Tesouro Nacional",
                indexador="SELIC",
                taxa=Decimal("100.00"),
                data_vencimento=date(current_year + 5, 3, 1),
            )

    print(f"Sucesso! Usuário '{user.username}' populado com receitas de ~R$ 20k, despesas de ~R$ 14k e R$ 168k aportados em 5 classes.")

def seed_demo_user():
    username = "demo_user"
    email = "demo@freecash.local"
    password = "password123"

    user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
    user.set_password(password)
    user.save()
    seed_user_data(user)

    # Se existir o usuário 'chrystian', popula ele também para que ambas as contas fiquem com os dados realistas
    user_chrystian = User.objects.filter(username="chrystian").first()
    if user_chrystian:
        seed_user_data(user_chrystian)

if __name__ == "__main__":
    seed_demo_user()
