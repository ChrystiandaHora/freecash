import pandas as pd
from datetime import date
from django.db import transaction
from django.conf import settings

from core.models import (
    Categoria,
    ConfigUsuario,
    ContaPagar,
    FormaPagamento,
    ResumoMensal,
    Transacao,
)


MESES_MAP = {
    "JANEIRO": 1,
    "FEVEREIRO": 2,
    "MARÇO": 3,
    "MARCO": 3,
    "ABRIL": 4,
    "MAIO": 5,
    "JUNHO": 6,
    "JULHO": 7,
    "AGOSTO": 8,
    "SETEMBRO": 9,
    "OUTUBRO": 10,
    "NOVEMBRO": 11,
    "DEZEMBRO": 12,
}


LINHAS_MAP = {
    "RECEITA": "receita",
    "OUTRAS RECEITAS": "outras_receitas",
    "GASTOS": "gastos",
}


def get_or_create_categorias_legado(usuario):
    categorias = {}

    categorias["RECEITA"], _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Receita",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )

    categorias["OUTRAS RECEITAS"], _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Outras Receitas",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )

    categorias["GASTOS"], _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Gastos",
        defaults={"tipo": Categoria.TIPO_DESPESA, "is_default": True},
    )

    return categorias


@transaction.atomic
def importar_planilha_excel(caminho_arquivo, usuario):
    xls = pd.ExcelFile(caminho_arquivo)

    categorias = get_or_create_categorias_legado(usuario)

    for aba in xls.sheet_names:
        ano = int(aba)  # abas são 2024 e 2025
        df = pd.read_excel(caminho_arquivo, sheet_name=aba)

        # Renomeia a primeira coluna
        df = df.rename(columns={df.columns[0]: "linha"})

        # Garante remoção de colunas vazias herdadas do Excel
        df = df.dropna(axis=1, how="all")

        # Garante remoção de linhas vazias
        df = df.dropna(subset=["linha"], how="all")

        # Normaliza nome das linhas
        df["linha"] = df["linha"].str.strip().str.upper()

        # Agora precisamos pegar RECEITA, OUTRAS RECEITAS, GASTOS
        dados_linhas = {
            "RECEITA": df[df["linha"] == "RECEITA"].iloc[0],
            "OUTRAS RECEITAS": df[df["linha"] == "OUTRAS RECEITAS"].iloc[0],
            "GASTOS": df[df["linha"] == "GASTOS"].iloc[0],
        }

        # Para cada mês existente nas colunas
        for col in df.columns[1:]:
            nome_mes = str(col).strip().upper()

            if nome_mes not in MESES_MAP:
                continue

            numero_mes = MESES_MAP[nome_mes]

            receita = float(dados_linhas["RECEITA"][col] or 0)
            outras = float(dados_linhas["OUTRAS RECEITAS"][col] or 0)
            gastos = float(dados_linhas["GASTOS"][col] or 0)
            total = receita + outras - gastos

            # Salva resumo mensal
            resumo, created = ResumoMensal.objects.update_or_create(
                usuario=usuario,
                ano=ano,
                mes=numero_mes,
                defaults={
                    "receita": receita,
                    "outras_receitas": outras,
                    "gastos": gastos,
                    "total": total,
                    "is_legacy": True,
                },
            )

            # Cria transações artificiais por linha
            if receita > 0:
                Transacao.objects.create(
                    usuario=usuario,
                    tipo=Transacao.TIPO_RECEITA,
                    data=date(ano, numero_mes, 1),
                    valor=receita,
                    descricao="Receita",
                    categoria=categorias["RECEITA"],
                    is_legacy=True,
                    origem_ano=ano,
                    origem_mes=numero_mes,
                    origem_linha="RECEITA",
                )

            if outras > 0:
                Transacao.objects.create(
                    usuario=usuario,
                    tipo=Transacao.TIPO_RECEITA,
                    data=date(ano, numero_mes, 1),
                    valor=outras,
                    descricao="Outras Receitas",
                    categoria=categorias["OUTRAS RECEITAS"],
                    is_legacy=True,
                    origem_ano=ano,
                    origem_mes=numero_mes,
                    origem_linha="OUTRAS RECEITAS",
                )

            if gastos > 0:
                Transacao.objects.create(
                    usuario=usuario,
                    tipo=Transacao.TIPO_DESPESA,
                    data=date(ano, numero_mes, 1),
                    valor=gastos,
                    descricao="Gastos",
                    categoria=categorias["GASTOS"],
                    is_legacy=True,
                    origem_ano=ano,
                    origem_mes=numero_mes,
                    origem_linha="GASTOS",
                )

    return True


@transaction.atomic
def importar_backup_excel(arquivo, usuario):
    xls = pd.ExcelFile(arquivo)

    # ---------- Aba: categorias ----------
    if "categorias" in xls.sheet_names:
        df_cat = pd.read_excel(arquivo, sheet_name="categorias")
        for _, row in df_cat.iterrows():
            Categoria.objects.update_or_create(
                usuario=usuario,
                nome=row["nome"],
                defaults={
                    "tipo": row.get("tipo", Categoria.TIPO_AMBOS),
                    "is_default": bool(row.get("is_default", False)),
                },
            )

    # ---------- Aba: formas_pagamento ----------
    if "formas_pagamento" in xls.sheet_names:
        df_fp = pd.read_excel(arquivo, sheet_name="formas_pagamento")
        for _, row in df_fp.iterrows():
            FormaPagamento.objects.update_or_create(
                usuario=usuario,
                nome=row["nome"],
                defaults={
                    "ativa": bool(row.get("ativa", True)),
                },
            )

    # ---------- Aba: transacoes ----------
    if "transacoes" in xls.sheet_names:
        df_trans = pd.read_excel(arquivo, sheet_name="transacoes")
        for _, row in df_trans.iterrows():
            categoria = None
            forma = None

            if row.get("categoria"):
                categoria = Categoria.objects.filter(
                    usuario=usuario, nome=row["categoria"]
                ).first()

            if row.get("forma_pagamento"):
                forma = FormaPagamento.objects.filter(
                    usuario=usuario, nome=row["forma_pagamento"]
                ).first()

            Transacao.objects.create(
                usuario=usuario,
                data=pd.to_datetime(row["data"]).date(),
                tipo=Transacao.TIPO_RECEITA
                if row["tipo"] == "Receita"
                else Transacao.TIPO_DESPESA,
                valor=float(row["valor"]),
                descricao=row.get("descricao", ""),
                categoria=categoria,
                forma_pagamento=forma,
                is_legacy=bool(row.get("is_legacy", False)),
                origem_ano=row.get("origem_ano"),
                origem_mes=row.get("origem_mes"),
                origem_linha=row.get("origem_linha"),
            )

    # ---------- Aba: contas_pagar ----------
    if "contas_pagar" in xls.sheet_names:
        df_cp = pd.read_excel(arquivo, sheet_name="contas_pagar")
        for _, row in df_cp.iterrows():
            categoria = None
            forma = None

            if row.get("categoria"):
                categoria = Categoria.objects.filter(
                    usuario=usuario, nome=row["categoria"]
                ).first()

            if row.get("forma_pagamento"):
                forma = FormaPagamento.objects.filter(
                    usuario=usuario, nome=row["forma_pagamento"]
                ).first()

            ContaPagar.objects.create(
                usuario=usuario,
                descricao=row["descricao"],
                valor=float(row["valor"]),
                data_vencimento=pd.to_datetime(row["data_vencimento"]).date(),
                status=row["status"],
                categoria=categoria,
                forma_pagamento=forma,
            )

    # ---------- Aba: resumo_mensal ----------
    if "resumo_mensal" in xls.sheet_names:
        df_rm = pd.read_excel(arquivo, sheet_name="resumo_mensal")
        for _, row in df_rm.iterrows():
            ResumoMensal.objects.update_or_create(
                usuario=usuario,
                ano=int(row["ano"]),
                mes=int(row["mes"]),
                defaults={
                    "receita": float(row["receita"]),
                    "outras_receitas": float(row["outras_receitas"]),
                    "gastos": float(row["gastos"]),
                    "total": float(row["total"]),
                    "is_legacy": False,
                },
            )

    # ---------- Aba: config_usuario ----------
    if "config_usuario" in xls.sheet_names:
        df_conf = pd.read_excel(arquivo, sheet_name="config_usuario")
        if not df_conf.empty:
            row = df_conf.iloc[0]
            config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
            config.moeda_padrao = row.get("moeda_padrao", "BRL")
            config.ultimo_export_em = (
                pd.to_datetime(row.get("ultimo_export_em"))
                if row.get("ultimo_export_em")
                else None
            )
            config.save()

    return True
