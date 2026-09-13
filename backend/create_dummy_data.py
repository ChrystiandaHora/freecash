"""Script para criação de usuário de teste com dados realistas cobrindo 12 meses.

Métricas:
- Receitas: ~ R$ 20.000,00/mês
- Gastos: ~ R$ 14.000,00/mês
- Investimentos: R$ 168.000,00 (20% em cada uma das 5 classes)
- Proventos contínuos em 12 meses e consolidação via CarteiraHistoricoService
"""

import calendar
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freecash.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import CartaoCredito, Categoria, ConfigUsuario, Conta, LancamentoRecorrente
from core.services.fatura_service import deduplicar_faturas
from investimento.models import (
    Ativo, Carteira, CarteiraHistorico, Cotacao, DetalheRendaFixa,
    PosicaoCarteira, SubcategoriaAtivo, Transacao,
)
from investimento.services.carteira_historico_service import CarteiraHistoricoService
from investimento.signals import criar_classificacao_padrao

User = get_user_model()


def safe_date(year: int, month: int, day: int) -> date:
    """Retorna uma data válida limitando o dia ao número máximo de dias do mês."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def seed_user_data(user):
    """Gera 12 meses de dados realistas e balanceados para o usuário informado."""
    print(f"Populando dados realistas de 12 meses para o usuário '{user.username}'...")

    if not user.classes_ativos.exists():
        criar_classificacao_padrao(sender=User, instance=user, created=True)

    # Limpeza atômica dos dados anteriores APENAS do usuário de teste informado
    for model in (Conta, CartaoCredito, Transacao, Ativo, CarteiraHistorico, LancamentoRecorrente):
        model.objects.filter(usuario=user).delete()

    today = date.today()

    # 1. Categorias Core
    cat_defs = [
        ("Salário & Pró-Labore", "R"), ("Consultoria & Serviços PJ", "R"), ("Rendimentos & Dividendos", "R"),
        ("Moradia & Aluguel", "D"), ("Transporte & Veículo", "D"), ("Fatura Cartão de Crédito", "D"),
        ("Supermercado & Alimentação", "D"), ("Saúde & Seguros", "D"),
        ("Utilidades & Contas Básicas", "D"), ("Lazer & Assinaturas", "D"),
    ]
    cats = {n: Categoria.objects.get_or_create(usuario=user, nome=n, defaults={"tipo": t})[0] for n, t in cat_defs}

    # Helper conciso para criação de lançamentos
    def add_conta(tipo, desc, val, dt, cat, realizado=True, cartao=None, eh_fat=False, dt_compra=None):
        return Conta.objects.create(
            usuario=user, tipo=tipo, descricao=desc, valor=val, data_prevista=dt,
            transacao_realizada=realizado, data_realizacao=dt if realizado else None,
            categoria=cat, cartao=cartao, eh_fatura_cartao=eh_fat, data_compra=dt_compra,
        )

    # 2. Cartões de Crédito
    c_plat = CartaoCredito.objects.create(usuario=user, nome="Cartão Platinum Prime", limite=Decimal("35000.00"), dia_fechamento=15, dia_vencimento=25, ativo=True)
    c_black = CartaoCredito.objects.create(usuario=user, nome="Cartão Black Executivo", limite=Decimal("45000.00"), dia_fechamento=25, dia_vencimento=5, ativo=True)

    # 3. Lançamentos mensais (12 meses: do mais antigo até hoje)
    consult_vals = [Decimal(v) for v in ("4200", "4400", "4150", "4500", "4300", "4250", "4600", "4100", "4350", "4450", "4200", "4300")]
    mercado_vals = [Decimal(v) for v in ("1420", "1480", "1390", "1510", "1450", "1430", "1530", "1400", "1460", "1490", "1440", "1450")]
    luz_vals = [Decimal(v) for v in ("235", "245", "220", "260", "230", "240", "255", "225", "240", "250", "235", "240")]

    for m_offset in range(11, -1, -1):
        idx = 11 - m_offset
        is_cur = (m_offset == 0)
        ref = today - relativedelta(months=m_offset)
        ref_prev = ref - relativedelta(months=1)
        y, m = ref.year, ref.month

        # Receitas (~ R$ 20k/mês)
        add_conta("R", "Salário & Remuneração Mensal", Decimal("14500.00"), safe_date(y, m, 5), cats["Salário & Pró-Labore"], not is_cur or today.day >= 5)
        add_conta("R", "Consultoria Especializada PJ", consult_vals[idx], safe_date(y, m, 12), cats["Consultoria & Serviços PJ"], not is_cur or today.day >= 12)
        add_conta("R", "Rendimentos FIIs & Dividendos Ações", Decimal(str(850 + idx * 39)), safe_date(y, m, 15), cats["Rendimentos & Dividendos"], not is_cur or today.day >= 15)

        # Despesas Fixas e Contas (~ R$ 14k/mês)
        add_conta("D", "Aluguel & Condomínio Residencial", Decimal("4200.00"), safe_date(y, m, 10), cats["Moradia & Aluguel"], not is_cur or today.day >= 10)
        add_conta("D", "Financiamento Parcela Veículo", Decimal("1850.00"), safe_date(y, m, 14), cats["Transporte & Veículo"], not is_cur or today.day >= 14)
        add_conta("D", "Supermercado Mensal & Hortifruti", mercado_vals[idx], safe_date(y, m, 18), cats["Supermercado & Alimentação"], not is_cur or today.day >= 18)
        add_conta("D", "Plano de Saúde Familiar Executivo", Decimal("680.00"), safe_date(y, m, 8), cats["Saúde & Seguros"], not is_cur or today.day >= 8)
        add_conta("D", "Assinaturas de Software & Streaming", Decimal("320.00"), safe_date(y, m, 20), cats["Lazer & Assinaturas"], not is_cur)

        # Utilidades
        if not is_cur:
            add_conta("D", "Internet Fibra Óptica 1Gbps", Decimal("190.00"), safe_date(y, m, 20), cats["Utilidades & Contas Básicas"])
            add_conta("D", "Energia Elétrica Concessionária", luz_vals[idx], safe_date(y, m, 22), cats["Utilidades & Contas Básicas"])
        else:
            add_conta("D", "Internet Fibra Óptica 1Gbps", Decimal("190.00"), today, cats["Utilidades & Contas Básicas"], realizado=False)
            add_conta("D", "Energia Elétrica Concessionária", Decimal("240.00"), today - timedelta(days=2), cats["Utilidades & Contas Básicas"], realizado=False)

        # Cartão Black Executivo (fechamento 25, vencimento 5)
        dt_black = safe_date(y, m, 5)
        pg_black = not is_cur or today.day >= 5
        add_conta("D", f"Fatura Cartão Black Executivo{' - ' + f'{m:02d}/{y}' if not is_cur else ''}", Decimal("2400.00"), dt_black, cats["Fatura Cartão de Crédito"], realizado=pg_black, cartao=c_black, eh_fat=True)
        add_conta("D", "Combustível & Serviços Automotivos", Decimal("380.00"), dt_black, cats["Transporte & Veículo"], realizado=pg_black, cartao=c_black, dt_compra=safe_date(ref_prev.year, ref_prev.month, 10))
        add_conta("D", "Restaurantes Executivos & Cafés", Decimal("420.00"), dt_black, cats["Supermercado & Alimentação"], realizado=pg_black, cartao=c_black, dt_compra=safe_date(ref_prev.year, ref_prev.month, 18))

        # Cartão Platinum Prime (fechamento 15, vencimento 25)
        dt_plat = safe_date(y, m, 25)
        if not is_cur:
            add_conta("D", f"Fatura Cartão Platinum Prime - {m:02d}/{y}", Decimal("3100.00"), dt_plat, cats["Fatura Cartão de Crédito"], cartao=c_plat, eh_fat=True)
            add_conta("D", "Compras Online & Tecnologia", Decimal("790.00"), dt_plat, cats["Lazer & Assinaturas"], cartao=c_plat, dt_compra=safe_date(y, m, 5))
            add_conta("D", "Supermercado Gourmet & Empório", Decimal("490.00"), dt_plat, cats["Supermercado & Alimentação"], cartao=c_plat, dt_compra=safe_date(y, m, 10))
        else:
            add_conta("D", "Fatura Cartão Platinum Prime", Decimal("3100.00"), dt_plat, cats["Fatura Cartão de Crédito"], realizado=False, cartao=c_plat, eh_fat=True)
            add_conta("D", "Jantar Restaurante Empório", Decimal("380.00"), dt_plat, cats["Supermercado & Alimentação"], cartao=c_plat, dt_compra=today - timedelta(days=3))
            add_conta("D", "Passagens Aéreas Férias", Decimal("1850.00"), dt_plat, cats["Lazer & Assinaturas"], cartao=c_plat, dt_compra=today - timedelta(days=7))
            add_conta("D", "Manutenção Preventiva Carro", Decimal("870.00"), dt_plat, cats["Transporte & Veículo"], cartao=c_plat, dt_compra=today - timedelta(days=10))

    deduplicar_faturas(user)

    # 4. Investimentos (R$ 168.000,00 distribuído em 20% por classe)
    def get_sub(cls_pat, sub_pat=None):
        qs = SubcategoriaAtivo.objects.filter(usuario=user, categoria__classe__nome__icontains=cls_pat)
        return (qs.filter(nome__icontains=sub_pat).first() if sub_pat else qs.first()) or SubcategoriaAtivo.objects.filter(usuario=user).first()

    sub_rf = get_sub("Renda Fixa")
    sub_acoes = get_sub("Renda Variável", "Ações")
    sub_fii = get_sub("Renda Variável", "FII")
    sub_inter = SubcategoriaAtivo.objects.filter(usuario=user, nome__iregex=r"BDR|Internacional|ETF").first() or sub_acoes
    sub_cripto = get_sub("Cripto")

    carteira_xp = Carteira.padrao_de(user)
    carteira_xp.nome, carteira_xp.instituicao, carteira_xp.cor, carteira_xp.meta_porcentagem = "Custódia Alpha Capital", "Alpha", "#0F0F0F", Decimal("60.00")
    carteira_xp.save()

    carteira_inter, _ = Carteira.objects.get_or_create(
        usuario=user, nome="Banco Digital Horizon",
        defaults={"instituicao": "Horizon", "cor": "#FF7A00", "meta_porcentagem": Decimal("40.00"), "considerar_no_saldo": True, "ordem": 1},
    )

    assets_def = [
        ("SELIC2029", "Tesouro Selic 2029", sub_rf, Decimal("2.24"), Decimal("15000.00"), Decimal("15450.00"), Decimal("20.00"), "inter"),
        ("VALE3", "Vale S.A.", sub_acoes, Decimal("250"), Decimal("60.00"), Decimal("63.80"), Decimal("9.00"), "xp"),
        ("ITUB4", "Itaú Unibanco Holding S.A.", sub_acoes, Decimal("400"), Decimal("31.50"), Decimal("34.25"), Decimal("7.50"), "xp"),
        ("WEGE3", "WEG S.A.", sub_acoes, Decimal("150"), Decimal("40.00"), Decimal("43.40"), Decimal("3.50"), "xp"),
        ("HGLG11", "CSHG Logística FII", sub_fii, Decimal("100"), Decimal("160.00"), Decimal("166.20"), Decimal("10.00"), "xp"),
        ("KNCR11", "Kinea Rendimentos Imobiliários FII", sub_fii, Decimal("120"), Decimal("100.00"), Decimal("103.50"), Decimal("7.00"), "xp"),
        ("MXRF11", "Maxi Renda FII", sub_fii, Decimal("560"), Decimal("10.00"), Decimal("10.48"), Decimal("3.00"), "xp"),
        ("IVVB11", "iShares S&P 500 Fundo de Índice", sub_inter, Decimal("60"), Decimal("360.00"), Decimal("385.00"), Decimal("13.00"), "xp"),
        ("AAPL34", "Apple Inc. BDR", sub_inter, Decimal("200"), Decimal("60.00"), Decimal("65.10"), Decimal("7.00"), "xp"),
        ("BTC", "Bitcoin (BTC)", sub_cripto, Decimal("0.08"), Decimal("320000.00"), Decimal("352000.00"), Decimal("15.00"), "xp"),
        ("ETH", "Ethereum (ETH)", sub_cripto, Decimal("0.50"), Decimal("16000.00"), Decimal("18200.00"), Decimal("5.00"), "xp"),
    ]

    data_inicio_invest = today - timedelta(days=365)

    for ticker, nome, sub, qtd, pm, cot, meta, cart_key in assets_def:
        carteira = carteira_xp if cart_key == "xp" else carteira_inter
        ativo = Ativo.objects.create(usuario=user, ticker=ticker, nome=nome, subcategoria=sub, quantidade=qtd, preco_medio=pm)

        # Ordem de compra inicial há 1 ano
        Transacao.objects.create(usuario=user, ativo=ativo, carteira=carteira, tipo="C", data=data_inicio_invest, quantidade=qtd, preco_unitario=pm, valor_total=qtd * pm)

        # Cotações históricas mensais
        for m_offset in range(11, 0, -1):
            ref = today - relativedelta(months=m_offset)
            prog = Decimal(str(round((11 - m_offset) / 11.0, 4)))
            val_cot = (pm * Decimal("0.96") + (cot - pm * Decimal("0.96")) * prog).quantize(Decimal("0.01"))
            Cotacao.objects.create(ativo=ativo, data=safe_date(ref.year, ref.month, 28), valor=val_cot)
        Cotacao.objects.create(ativo=ativo, data=today, valor=cot)

        # Proventos mensais (dividendos)
        if ticker in ["HGLG11", "KNCR11", "MXRF11", "ITUB4", "VALE3"]:
            unit = Decimal("1.25") if "11" in ticker else Decimal("0.65")
            for m_offset in range(11, -1, -1):
                ref = today - relativedelta(months=m_offset)
                dt_div = safe_date(ref.year, ref.month, min(today.day, 10) if (m_offset == 0 and today.day < 15) else 15)
                growth = Decimal(str(round(0.85 + ((11 - m_offset) / 11.0) * 0.30, 4)))
                pu = (unit * growth).quantize(Decimal("0.01"))
                Transacao.objects.create(usuario=user, ativo=ativo, carteira=carteira, tipo="D", data=dt_div, quantidade=qtd, preco_unitario=pu, valor_total=(qtd * pu).quantize(Decimal("0.01")))

        PosicaoCarteira.objects.filter(carteira=carteira, ativo=ativo).update(meta_porcentagem=meta)
        if "SELIC" in ticker:
            DetalheRendaFixa.objects.create(ativo=ativo, emissor="Tesouro Nacional", indexador="SELIC", taxa=Decimal("100.00"), data_vencimento=date(today.year + 5, 3, 1))

    # 5. Snapshots patrimoniais consolidados
    CarteiraHistoricoService(user).atualizar()
    print(f"Sucesso! Usuário '{user.username}' populado com 12 meses de dados (~R$ 20k rec, ~R$ 14k desp, R$ 168k inv).")


def criar_ou_atualizar_usuario_teste(username: str, email: str, password: str = "password123"):
    """Cria ou atualiza uma conta de teste isolada com e-mail confirmado."""
    user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
    user.email = email
    user.set_password(password)
    user.is_active = True
    user.save()

    config, _ = ConfigUsuario.objects.get_or_create(usuario=user)
    config.email_verificado = True
    config.email_verificado_em = timezone.now()
    config.save()

    seed_user_data(user)
    return user


if __name__ == "__main__":
    # Permite passar argumentos CLI opcionais: python create_dummy_data.py [usuario] [senha]
    alvo_username = sys.argv[1] if len(sys.argv) > 1 else "teste"
    alvo_senha = sys.argv[2] if len(sys.argv) > 2 else "password123"

    print("=" * 65)
    print("  SEMAPHORE / SEEDER DE DADOS DE TESTE (12 MESES)")
    print("=" * 65)

    # Popula a conta 'teste' solicitada
    user_teste = criar_ou_atualizar_usuario_teste(
        username=alvo_username,
        email=f"{alvo_username}@freecash.local",
        password=alvo_senha,
    )

    # Cria também 'demo_user' se o alvo for o padrão 'teste' para total conveniência
    if alvo_username == "teste":
        criar_ou_atualizar_usuario_teste(
            username="demo_user",
            email="demo@freecash.local",
            password="password123",
        )

    print("\n" + "=" * 65)
    print("  CONTA DE TESTE GERADA COM SUCESSO!")
    print(f"  - Usuário: {user_teste.username}  (ou demo_user)")
    print(f"  - Senha:   {alvo_senha}")
    print(f"  - E-mail:  {user_teste.email} (com verificação ativa)")
    print("=" * 65 + "\n")
