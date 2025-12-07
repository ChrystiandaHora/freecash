import pandas as pd
from datetime import date
from django.db import transaction
from django.conf import settings

from core.models import (
    Categoria,
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
        nome="Receita agregada",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )

    categorias["OUTRAS RECEITAS"], _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Outras receitas agregadas",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )

    categorias["GASTOS"], _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome="Gastos agregados",
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
                    descricao="Receita agregada",
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
                    descricao="Outras receitas agregadas",
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
                    descricao="Gastos agregados",
                    categoria=categorias["GASTOS"],
                    is_legacy=True,
                    origem_ano=ano,
                    origem_mes=numero_mes,
                    origem_linha="GASTOS",
                )

    return True
