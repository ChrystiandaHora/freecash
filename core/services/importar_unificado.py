from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from django.db import connection, transaction
from django.utils import timezone
from django.core.management.color import no_style

from core.models import (
    Categoria,
    Conta,
    FormaPagamento,
    ConfigUsuario,
    LogImportacao,
)
from core.services.import_planilha import importar_planilha_legado_padrao


# =========================================================
# Utilidades
# =========================================================


def advisory_lock(lock_id: int = 987654321) -> None:
    """
    Evita corrida se duas importações acontecerem ao mesmo tempo.
    Lock dura só até o final da transação atual.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])


def reset_sequences_for_models(*models) -> None:
    """
    Ajusta sequences do Postgres para o MAX(id) da tabela.
    Seguro mesmo com vários usuários (sequência é global por tabela).
    """
    sql_list = connection.ops.sequence_reset_sql(no_style(), models)
    if not sql_list:
        return
    with connection.cursor() as cursor:
        for sql in sql_list:
            cursor.execute(sql)


def parse_bool(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "sim"}


def parse_date(v: Any) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()

    s = str(v).strip()
    if not s:
        return None

    # tenta YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        pass

    # tenta timestamp “YYYY-MM-DD HH:MM:SS”
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").date()
    except Exception:
        return None


def parse_datetime(v: Any) -> Optional[datetime]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)

    s = str(v).strip()
    if not s:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def parse_decimal(v: Any) -> Decimal:
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

    # aceita "10,50" e "1.234,56"
    s = s.replace("R$", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


# =========================================================
# Detecção de arquivo
# =========================================================


def _lower_sheetnames(xls: pd.ExcelFile) -> set[str]:
    return {str(n).strip().lower() for n in xls.sheet_names}


def eh_backup_freecash(xls: pd.ExcelFile) -> bool:
    abas = _lower_sheetnames(xls)
    # backup atual (gerar_backup_excel novo)
    needed = {
        "metadata",
        "contas",
        "categorias",
        "formas_pagamento",
        "resumo_mensal",
        "configuracoes",
    }
    return needed.issubset(abas)


def eh_planilha_legado(xls: pd.ExcelFile) -> bool:
    for aba in xls.sheet_names:
        try:
            ano = int(str(aba).strip())
            if 1900 < ano < 2100:
                return True
        except Exception:
            pass
    return False


# =========================================================
# Import do backup FreeCash (XLSX)
# =========================================================


@dataclass
class ImportMaps:
    cat_old_to_new: Dict[int, int]
    fp_old_to_new: Dict[int, int]


def sobrescrever_dados_do_usuario(usuario) -> None:
    """
    Overwrite do usuário: apaga tudo que é dele.
    Importante: não mexe em dados de outros usuários.
    """
    Conta.objects.filter(created_by=usuario).delete()
    Categoria.objects.filter(created_by=usuario).delete()
    FormaPagamento.objects.filter(created_by=usuario).delete()
    # ConfigUsuario é OneToOne: vamos sobrescrever atualizando/criando, não delete obrigatório
    # mas pode deletar para ficar bem “limpo”
    ConfigUsuario.objects.filter(created_by=usuario).delete()


def importar_backup_freecash_xlsx(
    arquivo, usuario, sobrescrever: bool = True
) -> Dict[str, Any]:
    """
    Importa o XLSX gerado pelo gerar_backup_excel (FreeCash).
    Estratégia segura para multiusuário:
    - NÃO reaproveita IDs globais do arquivo (evita colisão com outros usuários)
    - cria Categorias e Formas primeiro e monta um mapa old_id -> new_id
    - cria Contas e ResumoMensal usando esse mapa
    - ConfigUsuario é recriado/atualizado
    """
    xls = pd.ExcelFile(arquivo)
    abas = _lower_sheetnames(xls)

    if not eh_backup_freecash(xls):
        raise ValueError(
            "Arquivo não parece ser um backup FreeCash válido (abas esperadas não encontradas)."
        )

    if sobrescrever:
        sobrescrever_dados_do_usuario(usuario)

    # 1) Categorias
    df_cat = pd.read_excel(arquivo, sheet_name="categorias", dtype=object)
    df_cat = df_cat.fillna("")
    cat_old_to_new: Dict[int, int] = {}

    # cria em massa
    cat_objs = []
    cat_rows = []
    for _, row in df_cat.iterrows():
        old_id = safe_int(row.get("id"))
        nome = str(row.get("nome") or "").strip()
        tipo = str(row.get("tipo") or "").strip()

        if not nome or tipo not in {
            Categoria.TIPO_RECEITA,
            Categoria.TIPO_DESPESA,
            Categoria.TIPO_INVESTIMENTO,
        }:
            continue

        cat = Categoria(
            created_by=usuario,
            nome=nome,
            tipo=tipo,
            is_default=parse_bool(row.get("is_default")),
        )
        cat_objs.append(cat)
        cat_rows.append(old_id)

    if cat_objs:
        created = Categoria.objects.bulk_create(cat_objs, batch_size=500)
        for old_id, obj in zip(cat_rows, created):
            if old_id is not None:
                cat_old_to_new[old_id] = obj.id

    # 2) Formas de pagamento
    df_fp = pd.read_excel(arquivo, sheet_name="formas_pagamento", dtype=object)
    df_fp = df_fp.fillna("")
    fp_old_to_new: Dict[int, int] = {}

    fp_objs = []
    fp_rows = []
    for _, row in df_fp.iterrows():
        old_id = safe_int(row.get("id"))
        nome = str(row.get("nome") or "").strip()
        if not nome:
            continue
        fp = FormaPagamento(
            created_by=usuario,
            nome=nome,
            ativa=parse_bool(row.get("ativa"))
            if str(row.get("ativa")).strip() != ""
            else True,
        )
        fp_objs.append(fp)
        fp_rows.append(old_id)

    if fp_objs:
        created = FormaPagamento.objects.bulk_create(fp_objs, batch_size=500)
        for old_id, obj in zip(fp_rows, created):
            if old_id is not None:
                fp_old_to_new[old_id] = obj.id

    maps = ImportMaps(cat_old_to_new=cat_old_to_new, fp_old_to_new=fp_old_to_new)

    # 3) Contas
    df_contas = pd.read_excel(arquivo, sheet_name="contas", dtype=object)
    df_contas = df_contas.fillna("")

    conta_objs = []
    for _, row in df_contas.iterrows():
        tipo = str(row.get("tipo") or "").strip()
        if tipo not in {
            Conta.TIPO_RECEITA,
            Conta.TIPO_DESPESA,
            Conta.TIPO_INVESTIMENTO,
        }:
            continue

        descricao = str(row.get("descricao") or "").strip()
        valor = parse_decimal(row.get("valor"))

        data_prevista = parse_date(row.get("data_prevista"))
        if not data_prevista:
            # sem data_prevista não dá para importar
            continue

        realizada = parse_bool(row.get("transacao_realizada"))
        data_realizacao = parse_date(row.get("data_realizacao")) if realizada else None

        old_cat_id = safe_int(row.get("categoria_id"))
        old_fp_id = safe_int(row.get("forma_pagamento_id"))
        new_cat_id = (
            maps.cat_old_to_new.get(old_cat_id) if old_cat_id is not None else None
        )
        new_fp_id = maps.fp_old_to_new.get(old_fp_id) if old_fp_id is not None else None

        conta = Conta(
            created_by=usuario,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
            data_prevista=data_prevista,
            transacao_realizada=realizada,
            data_realizacao=data_realizacao,
            categoria_id=new_cat_id,
            forma_pagamento_id=new_fp_id,
            is_legacy=parse_bool(row.get("is_legacy")),
            origem_ano=safe_int(row.get("origem_ano")),
            origem_mes=safe_int(row.get("origem_mes")),
            origem_linha=str(row.get("origem_linha") or "").strip() or None,
        )
        conta_objs.append(conta)

    if conta_objs:
        Conta.objects.bulk_create(conta_objs, batch_size=500)

    # 5) Config do usuário
    df_conf = pd.read_excel(arquivo, sheet_name="configuracoes", dtype=object)
    df_conf = df_conf.fillna("")
    moeda = "BRL"
    ultimo_export_em = None

    if len(df_conf) >= 1:
        # primeira linha de dados
        r0 = df_conf.iloc[0].to_dict()
        moeda = str(r0.get("moeda_padrao") or "BRL").strip() or "BRL"
        ultimo_export_em = parse_datetime(r0.get("ultimo_export_em"))

    ConfigUsuario.objects.update_or_create(
        created_by=usuario,
        defaults={
            "moeda_padrao": moeda,
            "ultimo_export_em": ultimo_export_em,
        },
    )

    # Opcional (higiene): ajustar sequences
    reset_sequences_for_models(Categoria, FormaPagamento, Conta, ConfigUsuario)

    return {
        "tipo": "backup",
        "msg": "Backup FreeCash importado com overwrite do usuário.",
        "counts": {
            "categorias": len(cat_old_to_new),
            "formas_pagamento": len(fp_old_to_new),
            "contas": len(conta_objs),
        },
    }


# =========================================================
# Import Unificado (router)
# =========================================================


@transaction.atomic
def importar_planilha_unificada(
    arquivo, usuario, sobrescrever: bool = True
) -> Dict[str, Any]:
    """
    Decide se o arquivo é:
    - backup FreeCash (xlsx gerado pelo app)
    - planilha legado (abas por ano)
    e executa overwrite do usuário (sobrescrever=True).
    Sempre registra LogImportacao.
    """
    advisory_lock(987654321)

    # Detecta por extensão e tenta abrir com pandas
    nome = (getattr(arquivo, "name", "") or "").lower()

    if not (nome.endswith(".xlsx") or nome.endswith(".xlsm") or nome.endswith(".xls")):
        # você pode adicionar CSV aqui depois
        raise ValueError("Formato não suportado no unificado. Envie .xlsx.")

    xls = pd.ExcelFile(arquivo)

    try:
        if eh_backup_freecash(xls):
            resultado = importar_backup_freecash_xlsx(
                arquivo, usuario, sobrescrever=sobrescrever
            )
            LogImportacao.objects.create(
                created_by=usuario,
                tipo=LogImportacao.TIPO_BACKUP,
                sucesso=True,
                mensagem=resultado.get("msg") or "Backup importado com sucesso.",
            )
            return resultado

        if eh_planilha_legado(xls):
            if sobrescrever:
                # legado já tem opção sobrescrever; garantimos aqui
                importar_planilha_legado_padrao(arquivo, usuario, sobrescrever=True)
            else:
                importar_planilha_legado_padrao(arquivo, usuario, sobrescrever=False)

            LogImportacao.objects.create(
                created_by=usuario,
                tipo=LogImportacao.TIPO_LEGADO,
                sucesso=True,
                mensagem="Planilha legado importada com sucesso (overwrite do usuário)."
                if sobrescrever
                else "Planilha legado importada (sem overwrite).",
            )
            return {"tipo": "legado", "msg": "Planilha legado importada com sucesso."}

        raise ValueError(
            "Arquivo não reconhecido: não parece ser backup FreeCash nem planilha legado."
        )

    except Exception as e:
        # registra erro
        LogImportacao.objects.create(
            created_by=usuario,
            tipo=LogImportacao.TIPO_BACKUP,  # default
            sucesso=False,
            mensagem=str(e),
        )
        raise
