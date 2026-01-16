from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple, List
import io
import pandas as pd
import uuid

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
from core.services.encryption import decrypt_from_zip


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


def safe_uuid(v: Any) -> Optional[uuid.UUID]:
    if not v:
        return None
    try:
        return uuid.UUID(str(v))
    except ValueError:
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
# Import do backup FreeCash (XLSX) - UPSERT STRATEGY
# =========================================================


def importar_backup_freecash_upsert(arquivo_io, usuario) -> Dict[str, Any]:
    """
    Importa backup usando estratégia UPSERT baseada em UUIDs.
    NÃO apaga dados existentes, apenas atualiza ou cria.
    """
    xls = pd.ExcelFile(arquivo_io)

    if not eh_backup_freecash(xls):
        raise ValueError("Arquivo não possui as abas necessárias para backup FreeCash.")

    # Reads all UUID maps first to allow easy FK resolution
    # In this robust version, we rely on the UUIDs present in the file.

    counts = {
        "categorias_created": 0,
        "categorias_updated": 0,
        "formas_created": 0,
        "formas_updated": 0,
        "contas_created": 0,
        "contas_updated": 0,
    }

    # 1) Categorias
    df_cat = pd.read_excel(arquivo_io, sheet_name="categorias", dtype=object).fillna("")

    for _, row in df_cat.iterrows():
        uid = safe_uuid(row.get("uuid"))
        if not uid:
            continue  # Skip if no UUID (can't upsert reliably without it)

        nome = str(row.get("nome") or "").strip()
        tipo = str(row.get("tipo") or "").strip()

        defaults = {
            "nome": nome,
            "tipo": tipo,
            "is_default": parse_bool(row.get("is_default")),
        }

        # Check if created/updated time exists in file? We usually don't overwrite these unless essential
        # But for full restore, maybe we should. For now let's keep auto_now behaviors unless specified.

        obj, created = Categoria.objects.update_or_create(
            uuid=uid, defaults=dict(usuario=usuario, **defaults)
        )
        if created:
            counts["categorias_created"] += 1
        else:
            counts["categorias_updated"] += 1

    # 2) Formas de pagamento
    df_fp = pd.read_excel(
        arquivo_io, sheet_name="formas_pagamento", dtype=object
    ).fillna("")

    for _, row in df_fp.iterrows():
        uid = safe_uuid(row.get("uuid"))
        if not uid:
            continue

        nome = str(row.get("nome") or "").strip()

        defaults = {
            "nome": nome,
            "ativa": parse_bool(row.get("ativa"))
            if str(row.get("ativa")).strip() != ""
            else True,
        }

        obj, created = FormaPagamento.objects.update_or_create(
            uuid=uid, defaults=dict(usuario=usuario, **defaults)
        )
        if created:
            counts["formas_created"] += 1
        else:
            counts["formas_updated"] += 1

    # 3) Contas
    df_contas = pd.read_excel(arquivo_io, sheet_name="contas", dtype=object).fillna("")

    # Pre-fetch UUID->ID maps for FKs
    cat_map = {str(c.uuid): c.id for c in Categoria.objects.filter(usuario=usuario)}
    fp_map = {str(f.uuid): f.id for f in FormaPagamento.objects.filter(usuario=usuario)}

    for _, row in df_contas.iterrows():
        uid = safe_uuid(row.get("uuid"))
        if not uid:
            continue

        tipo = str(row.get("tipo") or "").strip()
        descricao = str(row.get("descricao") or "").strip()
        valor = parse_decimal(row.get("valor"))
        data_prevista = parse_date(row.get("data_prevista"))

        if not data_prevista:
            continue

        realizada = parse_bool(row.get("transacao_realizada"))
        data_realizacao = parse_date(row.get("data_realizacao")) if realizada else None

        cat_uuid_str = str(row.get("categoria_uuid") or "")
        fp_uuid_str = str(row.get("forma_pagamento_uuid") or "")

        cat_id = cat_map.get(cat_uuid_str)
        fp_id = fp_map.get(fp_uuid_str)

        defaults = {
            "tipo": tipo,
            "descricao": descricao,
            "valor": valor,
            "data_prevista": data_prevista,
            "transacao_realizada": realizada,
            "data_realizacao": data_realizacao,
            "categoria_id": cat_id,
            "forma_pagamento_id": fp_id,
            "is_legacy": parse_bool(row.get("is_legacy")),
            "origem_ano": safe_int(row.get("origem_ano")),
            "origem_mes": safe_int(row.get("origem_mes")),
            "origem_linha": str(row.get("origem_linha") or "").strip() or None,
        }

        obj, created = Conta.objects.update_or_create(
            uuid=uid, defaults=dict(usuario=usuario, **defaults)
        )
        if created:
            counts["contas_created"] += 1
        else:
            counts["contas_updated"] += 1

    # 5) Config do usuário
    df_conf = pd.read_excel(
        arquivo_io, sheet_name="configuracoes", dtype=object
    ).fillna("")
    if len(df_conf) >= 1:
        r0 = df_conf.iloc[0].to_dict()
        uid = safe_uuid(r0.get("uuid"))
        moeda = str(r0.get("moeda_padrao") or "BRL").strip() or "BRL"
        ultimo_export_em = parse_datetime(r0.get("ultimo_export_em"))

        if uid:
            ConfigUsuario.objects.update_or_create(
                usuario=usuario,
                defaults={
                    "uuid": uid,  # Force UUID if provided (careful with uniqueness)
                    "moeda_padrao": moeda,
                    # We might not want to overwrite ultimo_export_em from backup, or maybe we do?
                    # Let's overwrite it as it is a restore state.
                    "ultimo_export_em": ultimo_export_em,
                },
            )
        else:
            # Fallback if no UUID in config
            ConfigUsuario.objects.update_or_create(
                usuario=usuario,
                defaults={"moeda_padrao": moeda, "ultimo_export_em": ultimo_export_em},
            )

    return {
        "tipo": "backup_upsert",
        "msg": "Backup FreeCash importado (Upsert - Atualizado/Criado).",
        "counts": counts,
    }


# =========================================================
# Import Unificado (router)
# =========================================================


@transaction.atomic
def importar_planilha_unificada(
    arquivo, usuario, sobrescrever: bool = True, password: str = None
) -> Dict[str, Any]:
    """
    Router unificado.
    Suporta:
    - Backup Zipado (criptografado) -> requer senha
    - Backup XLSX (novo formato com UUID) -> Upsert
    - Planilha legado -> (mantido como fallback)
    """
    advisory_lock(987654321)

    nome = (getattr(arquivo, "name", "") or "").lower()

    arquivo_processado = arquivo

    # 1. Decryption Handling
    if nome.endswith(".zip"):
        if not password:
            raise ValueError("Arquivo criptografado requer senha.")

        # Read file to bytes
        if hasattr(arquivo, "read"):
            arquivo.seek(0)
            file_bytes = arquivo.read()
        else:
            file_bytes = arquivo

        try:
            decrypted_files = decrypt_from_zip(file_bytes, password)
        except Exception:
            raise ValueError("Senha incorreta ou arquivo corrompido.")

        # Expecting valid xlsx inside
        # We take the first file ending with .xlsx
        xlsx_content = None
        for fname, content in decrypted_files.items():
            if fname.lower().endswith(".xlsx"):
                xlsx_content = content
                break

        if not xlsx_content:
            raise ValueError(
                "Nenhum arquivo .xlsx encontrado dentro do backup criptografado."
            )

        # Create bytes buffer for pandas
        arquivo_processado = io.BytesIO(xlsx_content)

    # 2. Processing
    xls = pd.ExcelFile(arquivo_processado)

    try:
        if eh_backup_freecash(xls):
            # NEW LOGIC: Upsert
            resultado = importar_backup_freecash_upsert(arquivo_processado, usuario)

            LogImportacao.objects.create(
                usuario=usuario,
                tipo=LogImportacao.TIPO_BACKUP,
                sucesso=True,
                mensagem=resultado.get("msg"),
            )
            return resultado

        if eh_planilha_legado(xls):
            # OLD LOGIC: Legacy
            # Legacy imports might not have UUIDs, and logic is different.
            # We keep sobrescrever param support here as requested?
            # User turned this into "secure" request, meaning they probably want new format.
            # But let's allow legacy for old files.

            if sobrescrever:
                importar_planilha_legado_padrao(arquivo, usuario, sobrescrever=True)
            else:
                importar_planilha_legado_padrao(arquivo, usuario, sobrescrever=False)

            LogImportacao.objects.create(
                usuario=usuario,
                tipo=LogImportacao.TIPO_LEGADO,
                sucesso=True,
                mensagem="Planilha legado importada com sucesso.",
            )
            return {"tipo": "legado", "msg": "Planilha legado importada com sucesso."}

        raise ValueError(
            "Arquivo não reconhecido: não parece ser backup FreeCash válido."
        )

    except Exception as e:
        LogImportacao.objects.create(
            usuario=usuario,
            tipo=LogImportacao.TIPO_BACKUP,
            sucesso=False,
            mensagem=str(e),
        )
        raise
