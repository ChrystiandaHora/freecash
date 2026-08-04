"""
Script para criação de usuário de teste 'demo_user' com dados 100% fictícios.

Métricas simuladas conforme requisitos do usuário:
- Receitas mensais: R$ 89.000,00 (> R$ 80.000,00)
- Gastos mensais: R$ 61.200,00 (> R$ 50.000,00)
- Investimentos total patrimonial: R$ 1.080.000,00
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
    SubcategoriaAtivo,
    Ativo,
    DetalheRendaFixa,
    Cotacao,
    Transacao,
)

User = get_user_model()

def seed_demo_user():
    username = "demo_user"
    email = "demo@freecash.local"
    password = "password123"

    # Reset or create demo_user
    user, created = User.objects.get_or_create(username=username, defaults={"email": email})
    user.set_password(password)
    user.save()

    print(f"User '{username}' created/updated with password '{password}'")

    # Clear previous demo data for clean state
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
    cat_desp_financiamento, _ = Categoria.objects.get_or_create(usuario=user, nome="Financiamento Imobiliário", defaults={"tipo": "D"})
    cat_desp_cartao, _ = Categoria.objects.get_or_create(usuario=user, nome="Fatura Cartão de Crédito", defaults={"tipo": "D"})
    cat_desp_alimentacao, _ = Categoria.objects.get_or_create(usuario=user, nome="Supermercado & Alimentação", defaults={"tipo": "D"})
    cat_desp_saude, _ = Categoria.objects.get_or_create(usuario=user, nome="Saúde & Seguros", defaults={"tipo": "D"})
    cat_desp_lazer, _ = Categoria.objects.get_or_create(usuario=user, nome="Lazer & Viagens", defaults={"tipo": "D"})

    # 2. Cartões & Contas Bancárias (Ajustes de Pagamentos)
    c_itau = CartaoCredito.objects.create(
        usuario=user,
        nome="Itaú Personnalité Black",
        limite=Decimal("95000.00"),
        dia_fechamento=25,
        dia_vencimento=5,
        ativo=True,
    )
    c_nubank = CartaoCredito.objects.create(
        usuario=user,
        nome="Nubank Ultravioleta",
        limite=Decimal("50000.00"),
        dia_fechamento=15,
        dia_vencimento=25,
        ativo=True,
    )
    c_btg = CartaoCredito.objects.create(
        usuario=user,
        nome="BTG Pactual Black",
        limite=Decimal("120000.00"),
        dia_fechamento=20,
        dia_vencimento=30,
        ativo=True,
    )

    # 3. Receitas (> R$ 80.000,00 -> Total R$ 89.000,00)
    d1 = date(current_year, current_month, 5)
    d2 = date(current_year, current_month, 10)
    d3 = date(current_year, current_month, 15)

    Conta.objects.create(
        usuario=user,
        tipo="R",
        descricao="Salário Diretoria Executiva",
        valor=Decimal("58500.00"),
        data_prevista=d1,
        transacao_realizada=True,
        data_realizacao=d1,
        categoria=cat_rec_salario,
    )
    Conta.objects.create(
        usuario=user,
        tipo="R",
        descricao="Contrato Consultoria TI Enterprise",
        valor=Decimal("24000.00"),
        data_prevista=d2,
        transacao_realizada=True,
        data_realizacao=d2,
        categoria=cat_rec_consultoria,
    )
    Conta.objects.create(
        usuario=user,
        tipo="R",
        descricao="Distribuição de Dividendos FIIs/Ações",
        valor=Decimal("6500.00"),
        data_prevista=d3,
        transacao_realizada=True,
        data_realizacao=d3,
        categoria=cat_rec_proventos,
    )

    # 4. Gastos / Despesas (> R$ 50.000,00 -> Total R$ 61.200,00)
    dt_moradia = date(current_year, current_month, 8)
    dt_finan = date(current_year, current_month, 12)
    dt_itau = date(current_year, current_month, 5)
    dt_nubank = date(current_year, current_month, 25)
    dt_mercado = date(current_year, current_month, 18)
    dt_saude = date(current_year, current_month, 10)

    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Aluguel & Condomínio Residencial Alphaville",
        valor=Decimal("14500.00"),
        data_prevista=dt_moradia,
        transacao_realizada=True,
        data_realizacao=dt_moradia,
        categoria=cat_desp_moradia,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Financiamento Imobiliário Casa de Campo",
        valor=Decimal("12000.00"),
        data_prevista=dt_finan,
        transacao_realizada=True,
        data_realizacao=dt_finan,
        categoria=cat_desp_financiamento,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Fatura Itaú Personnalité Black",
        valor=Decimal("18500.00"),
        data_prevista=dt_itau,
        transacao_realizada=True,
        data_realizacao=dt_itau,
        categoria=cat_desp_cartao,
        cartao=c_itau,
        eh_fatura_cartao=True,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Fatura Nubank Ultravioleta",
        valor=Decimal("8200.00"),
        data_prevista=dt_nubank,
        transacao_realizada=False,
        categoria=cat_desp_cartao,
        cartao=c_nubank,
        eh_fatura_cartao=True,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Compras Supermercado Gourmet & Emporium",
        valor=Decimal("4800.00"),
        data_prevista=dt_mercado,
        transacao_realizada=True,
        data_realizacao=dt_mercado,
        categoria=cat_desp_alimentacao,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Plano de Saúde Familiar Bradesco Saúde Top",
        valor=Decimal("3200.00"),
        data_prevista=dt_saude,
        transacao_realizada=True,
        data_realizacao=dt_saude,
        categoria=cat_desp_saude,
    )

    # 5. Compras de Cartão (Conta com cartao e eh_fatura_cartao=False)
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Passagens Aéreas Executiva Paris",
        valor=Decimal("12500.00"),
        data_prevista=dt_itau,
        data_compra=today - timedelta(days=10),
        categoria=cat_desp_lazer,
        cartao=c_itau,
        eh_fatura_cartao=False,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Jantar Fasano Restaurante",
        valor=Decimal("1850.00"),
        data_prevista=dt_itau,
        data_compra=today - timedelta(days=5),
        categoria=cat_desp_alimentacao,
        cartao=c_itau,
        eh_fatura_cartao=False,
    )
    Conta.objects.create(
        usuario=user,
        tipo="D",
        descricao="Apple Store - MacBook Pro M3 Max",
        valor=Decimal("18900.00"),
        data_prevista=dt_nubank,
        data_compra=today - timedelta(days=12),
        categoria=cat_desp_lazer,
        cartao=c_nubank,
        eh_fatura_cartao=False,
    )

    # 6. Investimentos (Patrimônio Total ~ R$ 1.080.000,00)
    sub_acoes = SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="Ações").first()
    if not sub_acoes:
        sub_acoes = SubcategoriaAtivo.objects.filter(usuario=user).first()

    sub_fii = SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="FII").first() or sub_acoes
    sub_rf = SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="Tesouro").first() or sub_acoes
    sub_cripto = SubcategoriaAtivo.objects.filter(usuario=user, nome__icontains="Bitcoin").first() or sub_acoes

    # Definição dos ativos para somar exatamente ~ R$ 1.080.000,00 a mercado
    assets_def = [
        {"ticker": "VALE3", "nome": "Vale S.A.", "sub": sub_acoes, "qtd": Decimal("3500"), "pm": Decimal("60.00"), "cot": Decimal("64.20"), "meta": Decimal("20.00")},
        {"ticker": "PETR4", "nome": "Petróleo Brasileiro S.A.", "sub": sub_acoes, "qtd": Decimal("5000"), "pm": Decimal("35.00"), "cot": Decimal("38.50"), "meta": Decimal("20.00")},
        {"ticker": "ITUB4", "nome": "Itaú Unibanco Holding S.A.", "sub": sub_acoes, "qtd": Decimal("6000"), "pm": Decimal("30.00"), "cot": Decimal("33.80"), "meta": Decimal("20.00")},
        {"ticker": "HGLG11", "nome": "CSHG Logística FII", "sub": sub_fii, "qtd": Decimal("1000"), "pm": Decimal("160.00"), "cot": Decimal("168.50"), "meta": Decimal("15.00")},
        {"ticker": "KNCR11", "nome": "Kinea Rendimentos Imobiliários FII", "sub": sub_fii, "qtd": Decimal("1200"), "pm": Decimal("100.00"), "cot": Decimal("103.20"), "meta": Decimal("10.00")},
        {"ticker": "CDB-BTG", "nome": "CDB BTG Pactual 115% CDI", "sub": sub_rf, "qtd": Decimal("120"), "pm": Decimal("1000.00"), "cot": Decimal("1050.00"), "meta": Decimal("10.00")},
        {"ticker": "BTC", "nome": "Bitcoin (BTC)", "sub": sub_cripto, "qtd": Decimal("0.12"), "pm": Decimal("300000.00"), "cot": Decimal("347166.66"), "meta": Decimal("5.00")},
    ]

    for item in assets_def:
        ativo = Ativo.objects.create(
            usuario=user,
            ticker=item["ticker"],
            nome=item["nome"],
            subcategoria=item["sub"],
            meta_porcentagem=item["meta"],
            quantidade=item["qtd"],
            preco_medio=item["pm"],
        )

        # Cotação a mercado
        Cotacao.objects.create(
            ativo=ativo,
            data=today,
            valor=item["cot"],
        )

        # Ordem de compra inicial
        Transacao.objects.create(
            usuario=user,
            ativo=ativo,
            tipo="C",
            data=today - timedelta(days=90),
            quantidade=item["qtd"],
            preco_unitario=item["pm"],
            valor_total=item["qtd"] * item["pm"],
        )

        # Transações de proventos históricas (Efeito Bola de Neve)
        if item["ticker"] in ["PETR4", "ITUB4", "HGLG11", "KNCR11"]:
            for m in range(1, 7):
                dt_div = date(current_year, m, 15) if m <= current_month else date(current_year - 1, m + 6, 15)
                Transacao.objects.create(
                    usuario=user,
                    ativo=ativo,
                    tipo="D",
                    data=dt_div,
                    quantidade=item["qtd"],
                    preco_unitario=Decimal("1.35"),
                    valor_total=item["qtd"] * Decimal("1.35"),
                )

        if "CDB" in item["ticker"]:
            DetalheRendaFixa.objects.create(
                ativo=ativo,
                emissor="Banco BTG Pactual",
                indexador="CDI",
                taxa=Decimal("115.00"),
                data_vencimento=date(current_year + 3, 12, 31),
            )

    print("Demo user seeding completed successfully!")

if __name__ == "__main__":
    seed_demo_user()
