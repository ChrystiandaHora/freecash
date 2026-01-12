from decimal import Decimal, InvalidOperation
import pandas as pd
from django.db import transaction
from django.utils import timezone

from core.models import Categoria, Conta, FormaPagamento, ConfigUsuario


def _to_int(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "sim", "yes", "y"}


def _to_decimal(v):
    if v is None:
        return Decimal("0")
    try:
        if pd.isna(v):
            return Decimal("0")
    except Exception:
        pass

    if isinstance(v, (int, float, Decimal)):
        try:
            return Decimal(str(v))
        except Exception:
            return Decimal("0")

    s = str(v).strip()
    if not s:
        return Decimal("0")

    s = s.replace("R$", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _to_date(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


@transaction.atomic
def importar_backup_freecash_xlsx(arquivo, usuario, sobrescrever=True):
    if sobrescrever:
        Conta.objects.filter(created_by=usuario).delete()
        Categoria.objects.filter(created_by=usuario).delete()
        FormaPagamento.objects.filter(created_by=usuario).delete()
        ConfigUsuario.objects.filter(created_by=usuario).delete()

    xls = pd.ExcelFile(arquivo)

    # 1) Categorias
    df_cat = pd.read_excel(xls, sheet_name="categorias", dtype=object)
    for _, row in df_cat.iterrows():
        obj_id = _to_int(row.get("id"))
        nome = (row.get("nome") or "").strip()
        tipo = (row.get("tipo") or "").strip()
        is_default = _to_bool(row.get("is_default"))

        if not obj_id or not nome or not tipo:
            continue

        Categoria.objects.create(
            id=obj_id,
            created_by=usuario,
            nome=nome,
            tipo=tipo,
            is_default=is_default,
        )

    # 2) Formas de pagamento
    df_fp = pd.read_excel(xls, sheet_name="formas_pagamento", dtype=object)
    for _, row in df_fp.iterrows():
        obj_id = _to_int(row.get("id"))
        nome = (row.get("nome") or "").strip()
        ativa = _to_bool(row.get("ativa"))

        if not obj_id or not nome:
            continue

        FormaPagamento.objects.create(
            id=obj_id,
            created_by=usuario,
            nome=nome,
            ativa=ativa,
        )

    # 3) Contas
    df_contas = pd.read_excel(xls, sheet_name="contas", dtype=object)
    for _, row in df_contas.iterrows():
        obj_id = _to_int(row.get("id"))
        tipo = (row.get("tipo") or "").strip()
        descricao = (row.get("descricao") or "").strip()
        valor = _to_decimal(row.get("valor"))
        data_prevista = _to_date(row.get("data_prevista"))
        transacao_realizada = _to_bool(row.get("transacao_realizada"))
        data_realizacao = _to_date(row.get("data_realizacao"))

        categoria_id = _to_int(row.get("categoria_id"))
        forma_id = _to_int(row.get("forma_pagamento_id"))

        is_legacy = _to_bool(row.get("is_legacy"))
        origem_ano = _to_int(row.get("origem_ano"))
        origem_mes = _to_int(row.get("origem_mes"))
        origem_linha = (row.get("origem_linha") or "").strip() or None

        if not obj_id or not tipo or not data_prevista:
            continue

        if transacao_realizada and not data_realizacao:
            data_realizacao = data_prevista

        Conta.objects.create(
            id=obj_id,
            created_by=usuario,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
            data_prevista=data_prevista,
            transacao_realizada=transacao_realizada,
            data_realizacao=data_realizacao,
            categoria_id=categoria_id,
            forma_pagamento_id=forma_id,
            is_legacy=is_legacy,
            origem_ano=origem_ano,
            origem_mes=origem_mes,
            origem_linha=origem_linha,
        )

    # 5) Config
    df_conf = pd.read_excel(xls, sheet_name="configuracoes", dtype=object)
    moeda = "BRL"
    if len(df_conf) > 0:
        m = (df_conf.iloc[0].get("moeda_padrao") or "").strip()
        if m:
            moeda = m

    ConfigUsuario.objects.create(
        created_by=usuario,
        moeda_padrao=moeda,
        ultimo_export_em=timezone.now(),
    )

    return True
