"""Importação do backup completo do usuário a partir do ZIP gerado pela exportação.

Lê o `dados.json` de dentro do ZIP — cifrado com AES-256 ou não, já que um backup
extraído e recompactado numa ferramenta comum também precisa voltar — e substitui,
numa transação atômica, todas as entidades do usuário pelas do arquivo (ver
docs/backup.md).
"""

from __future__ import annotations

import json
import uuid
import logging
import zipfile

import pyzipper
from django.db import transaction
from django.utils import timezone
from django.db.models.fields.related import ForeignKey, OneToOneField

from core.services.export_service import FORMATO, get_backupable_models

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = {"5.0"}

# Teto do `dados.json` descompactado: barra ZIP malicioso que infla ao abrir (zip bomb)
TAMANHO_MAXIMO_DADOS_JSON = 100 * 1024 * 1024

ARQUIVO_DE_DADOS = "dados.json"


def ler_backup_zip(arquivo, senha: str | None) -> dict:
    """Extrai e valida o `dados.json` de um backup em ZIP.

    Aceita ZIP cifrado (AES-256 ou ZipCrypto) e ZIP sem senha.

    Raises:
        ValueError: Arquivo que não é ZIP, sem `dados.json`, senha ausente ou errada,
            conteúdo grande demais, ou formato/versão que não são deste sistema.

    Returns:
        dict: O conteúdo de `dados.json`.
    """
    try:
        with pyzipper.AESZipFile(arquivo) as zf:
            try:
                info = zf.getinfo(ARQUIVO_DE_DADOS)
            except KeyError:
                raise ValueError(
                    f"O ZIP não contém o arquivo {ARQUIVO_DE_DADOS}; não é um backup do freecash."
                )
            if info.file_size > TAMANHO_MAXIMO_DADOS_JSON:
                raise ValueError("O arquivo de dados do backup é grande demais para importar.")
            protegido = bool(info.flag_bits & 0x1)
            if protegido and not senha:
                raise ValueError("Este arquivo está protegido por senha. Informe a senha do backup.")
            if senha:
                zf.setpassword(senha.encode("utf-8"))
            try:
                with zf.open(info) as entrada:
                    # Lê um byte além do teto: o tamanho declarado no cabeçalho pode mentir
                    conteudo = entrada.read(TAMANHO_MAXIMO_DADOS_JSON + 1)
            except RuntimeError:
                raise ValueError("Senha incorreta.")
    except (zipfile.BadZipFile, pyzipper.BadZipFile):
        raise ValueError("O arquivo enviado não é um ZIP válido ou está corrompido.")

    if len(conteudo) > TAMANHO_MAXIMO_DADOS_JSON:
        raise ValueError("O arquivo de dados do backup é grande demais para importar.")
    try:
        data_dict = json.loads(conteudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f"O {ARQUIVO_DE_DADOS} do backup não é um JSON válido.")

    validar_formato(data_dict)
    return data_dict


def validar_formato(data_dict: dict) -> None:
    """Recusa conteúdo de outro sistema ou de versão que esta importação não conhece.

    Raises:
        ValueError: Formato ou versão não suportados.
    """
    metadata = data_dict.get("metadata") if isinstance(data_dict, dict) else None
    if not isinstance(metadata, dict) or metadata.get("formato") != FORMATO:
        raise ValueError("Este arquivo não foi gerado pelo freecash.")
    version = metadata.get("version")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Versão de backup não suportada: {version!r}. "
            f"Versões aceitas: {sorted(SUPPORTED_VERSIONS)}."
        )


# Campos que descrevem a conta, não os dados: o backup os carrega, mas a restauração
# mantém os atuais. Sem isto, um backup anterior à confirmação do e-mail a desfaz e a
# importação seguinte cai no portão de verificação (ver docs/backup.md).
CAMPOS_DE_ESTADO_DA_CONTA = {
    "ConfigUsuario": ("email_verificado", "email_verificado_em", "email_pendente"),
}


def _restaurar_linhas_extrato(registros: list, uuid_to_id: dict) -> tuple[int, int]:
    """Recria as linhas de extrato, religando extrato e conta pelos UUIDs do backup.

    Fica fora do laço genérico porque `LinhaExtrato` não tem FK para o usuário: pertence
    a ele através do `ExtratoImportado`. Linha cujo extrato não veio no backup é
    descartada, já que a FK é obrigatória; a conta vinculada é opcional e só se perde
    quando não existe mais.

    Returns:
        tuple[int, int]: Linhas restauradas e linhas ignoradas.
    """
    from decimal import Decimal

    from django.utils.dateparse import parse_date

    from core.models import LinhaExtrato

    extratos = uuid_to_id.get("core.ExtratoImportado", {})
    contas = uuid_to_id.get("core.Conta", {})
    restauradas = ignoradas = 0

    for row in registros:
        extrato_id = extratos.get(row.get("extrato_uuid"))
        if not extrato_id:
            ignoradas += 1
            continue
        try:
            LinhaExtrato.objects.update_or_create(
                uuid=row.get("uuid") or uuid.uuid4(),
                defaults={
                    "extrato_id": extrato_id,
                    "data": parse_date(row["data"]),
                    "descricao": row.get("descricao") or "",
                    "valor": Decimal(str(row.get("valor") or 0)),
                    "tipo": row.get("tipo") or LinhaExtrato.TIPO_DEBITO,
                    "status": row.get("status") or "pendente",
                    "conta_vinculada_id": contas.get(row.get("conta_vinculada_uuid")),
                },
            )
            restauradas += 1
        except Exception as e:
            logger.warning("Falha ao restaurar linha de extrato: %s", e)
            ignoradas += 1

    return restauradas, ignoradas


def restaurar_dados_usuario(data_dict: dict, user) -> dict:
    """Substitui transacionalmente todas as entidades do usuário com os dados do backup.

    Apaga os dados atuais e reinsere os do backup, religando as chaves estrangeiras
    pelos UUIDs estáveis do arquivo.

    Desconecta dois conjuntos de signals durante a operação. Os de investimento, para
    não recalcular preço médio parcialmente a cada transação reinserida — o recálculo é
    forçado no fim. E os de consolidação de fatura do core, porque o backup já traz as
    faturas com seus UUIDs, e o signal ativo criaria uma fatura fantasma que depois
    duplicaria a original.

    Returns:
        dict: Estatísticas com total de registros restaurados ou falhas.
    """
    # ── Desconectar signals de investimento durante a importação ─────────────
    # O signal post_save/post_delete de Transacao chama recalcular_ativo() a
    # cada registro inserido, produzindo valores parciais/incorretos de
    # quantidade e preco_medio durante o processo de restauração em lote.
    try:
        from django.db.models.signals import post_save, post_delete
        from investimento.signals import atualizar_ativo_apos_transacao
        from investimento.models import Transacao as TransacaoInvestimento

        post_save.disconnect(atualizar_ativo_apos_transacao, sender=TransacaoInvestimento)
        post_delete.disconnect(atualizar_ativo_apos_transacao, sender=TransacaoInvestimento)
        signals_disconnected = True
    except Exception as e:
        logger.warning("Não foi possível desconectar signals de investimento: %s", e)
        signals_disconnected = False

    # ── Desconectar signals de consolidação de fatura do core ────────────────
    # O post_save de Conta chama _consolidar_fatura() para cada compra de cartão
    # restaurada, criando uma fatura consolidada nova (com UUID gerado na hora).
    # Como o backup também contém a fatura original — restaurada por
    # update_or_create(uuid=...) — o resultado é uma fatura duplicada por mês.
    try:
        from core.signals import monitorar_salvamento_conta, monitorar_delecao_conta
        from core.models import Conta as ContaCore

        post_save.disconnect(monitorar_salvamento_conta, sender=ContaCore)
        post_delete.disconnect(monitorar_delecao_conta, sender=ContaCore)
        core_signals_disconnected = True
    except Exception as e:
        logger.warning("Não foi possível desconectar signals de fatura do core: %s", e)
        core_signals_disconnected = False

    backup_models = get_backupable_models()
    uuid_to_id = {}
    total_restored = 0
    total_ignorados = 0
    faturas_removidas = 0  # faturas de cartão duplicadas descartadas na normalização
    ativos_restaurados = []  # rastreia ativos para recálculo posterior

    def get_model_field_names(model):
        """Retorna os nomes de campos válidos do modelo."""
        return {f.name for f in model._meta.get_fields() if hasattr(f, "column")}

    def filter_valid_fields(model, row):
        """Filtra apenas campos que existem no modelo atual.

        Chave primária e dono nunca vêm do arquivo: o `dados.json` pode ser editado à
        mão, e um `usuario_id` ou `id` forjado gravaria na conta de outro usuário.
        """
        valid_fields = get_model_field_names(model)
        # Também incluir campos de FK com sufixo _id
        valid_fk_fields = {
            f"{f.name}_id" for f in model._meta.fields if isinstance(f, ForeignKey)
        }
        proibidos = {model._meta.pk.name, model._meta.pk.attname, "usuario", "usuario_id"}
        all_valid = (valid_fields | valid_fk_fields) - proibidos
        return {k: v for k, v in row.items() if k in all_valid}

    try:
        with transaction.atomic():
            # 1. DELETE EXISTING
            for model in reversed(backup_models):
                is_one_to_one = False
                for field in model._meta.fields:
                    if isinstance(field, OneToOneField) and field.name == "usuario":
                        is_one_to_one = True
                        break

                if not is_one_to_one:
                    deleted_count, _ = model.objects.filter(usuario=user).delete()
                    logger.debug(
                        "Removidos %d registros de %s para o usuário %s",
                        deleted_count, model.__name__, user.username
                    )

            for model in backup_models:
                # Chave única por app_label.model_name para evitar colisão entre apps
                uuid_to_id[f"{model._meta.app_label}.{model.__name__}"] = {}
                # Compatibilidade retroativa: manter também pela chave simples de nome
                uuid_to_id[model.__name__] = uuid_to_id[f"{model._meta.app_label}.{model.__name__}"]

            # 2. IMPORT NEW
            for model in backup_models:
                app_label = model._meta.app_label
                model_name = model.__name__
                composite_key = f"{app_label}.{model_name}"

                is_one_to_one_user = False
                for field in model._meta.fields:
                    if isinstance(field, OneToOneField) and field.name == "usuario":
                        is_one_to_one_user = True
                        break

                registros_do_app = data_dict.get("data", {}).get(app_label, {})
                records = registros_do_app.get(model_name, [])

                logger.debug(
                    "Restaurando %d registros de %s.%s", len(records), app_label, model_name
                )

                for row in records:
                    uid = row.pop("uuid", None)
                    if not uid:
                        total_ignorados += 1
                        continue

                    # Parse date/datetime fields from string to actual python objects
                    from django.db.models import DateField, DateTimeField
                    from django.utils.dateparse import parse_date, parse_datetime

                    for field in model._meta.fields:
                        if field.name in row and row[field.name]:
                            val = row[field.name]
                            if isinstance(val, str):
                                if isinstance(field, DateTimeField):
                                    parsed = parse_datetime(val)
                                    if parsed:
                                        row[field.name] = parsed
                                elif isinstance(field, DateField):
                                    parsed = parse_date(val)
                                    if parsed:
                                        row[field.name] = parsed

                    # Resolve FKs usando chave composta (app_label.ModelName)
                    for field in model._meta.fields:
                        if isinstance(field, ForeignKey) and field.name != "usuario":
                            fk_uuid_key = f"{field.name}_uuid"
                            val_uuid = row.pop(fk_uuid_key, None)

                            if val_uuid:
                                target_model = field.remote_field.model
                                target_key = f"{target_model._meta.app_label}.{target_model.__name__}"
                                local_id = uuid_to_id.get(target_key, {}).get(str(val_uuid))
                                if local_id is None:
                                    # Fallback: chave simples de nome
                                    local_id = uuid_to_id.get(target_model.__name__, {}).get(str(val_uuid))
                                row[f"{field.name}_id"] = local_id
                            else:
                                row[f"{field.name}_id"] = None

                    # Filtrar campos que não existem mais no modelo
                    row = filter_valid_fields(model, row)
                    preservados = CAMPOS_DE_ESTADO_DA_CONTA.get(model_name, ())
                    row = {k: v for k, v in row.items() if k not in preservados}

                    # Upsert/Create
                    obj = None
                    try:
                        if is_one_to_one_user:
                            obj, _ = model.objects.update_or_create(
                                usuario=user, defaults=row
                            )
                        else:
                            obj, _ = model.objects.update_or_create(
                                uuid=uid, usuario=user, defaults=row
                            )
                    except Exception as exc:
                        logger.warning(
                            "Falha no update_or_create de %s (uuid=%s): %s — tentando fallback por nome.",
                            model_name, uid, exc
                        )
                        # Fallback: correspondência por nome
                        nome = row.get("nome")
                        try:
                            if nome:
                                existing = model.objects.filter(usuario=user, nome=nome).first()
                                if existing:
                                    for k, v in row.items():
                                        setattr(existing, k, v)
                                    existing.save()
                                    obj = existing
                                else:
                                    row["uuid"] = uuid.uuid4()
                                    obj = model.objects.create(usuario=user, **row)
                            else:
                                row["uuid"] = uuid.uuid4()
                                obj = model.objects.create(usuario=user, **row)
                        except Exception as inner_exc:
                            logger.error(
                                "Falha crítica ao restaurar %s (uuid=%s): %s",
                                model_name, uid, inner_exc
                            )
                            total_ignorados += 1
                            continue

                    if obj is not None:
                        uuid_to_id[composite_key][str(uid)] = obj.id
                        uuid_to_id[model_name][str(uid)] = obj.id
                        total_restored += 1

                        # Rastrear ativos restaurados para recálculo posterior
                        if model_name == "Ativo":
                            ativos_restaurados.append(obj)

            # 2b. Restaurar o histórico de aportes das metas
            # Não passa pelo laço genérico porque `AporteMeta` não tem FK para o
            # usuário. Os registros antigos já sumiram junto com as metas, via
            # CASCADE, no passo de DELETE.
            aporte_records = data_dict.get("data", {}).get("core", {}).get("AporteMeta", [])
            if aporte_records:
                logger.debug("Restaurando %d registros de AporteMeta", len(aporte_records))
                from core.models import AporteMeta
                from django.utils.dateparse import parse_date
                from decimal import Decimal as DecimalAporte

                for row in aporte_records:
                    meta_uuid = row.get("meta_uuid")
                    meta_id = uuid_to_id.get("core.MetaFinanceira", {}).get(meta_uuid)
                    if not meta_id:
                        meta_id = uuid_to_id.get("MetaFinanceira", {}).get(meta_uuid)

                    if not meta_id:
                        total_ignorados += 1
                        continue

                    try:
                        data_aporte = parse_date(row["data"]) if row.get("data") else None
                        # `valor_acumulado` da meta já veio pronto do backup: os
                        # aportes são apenas o histórico e não devem ser somados
                        # de novo (a soma acontece só na action da API).
                        AporteMeta.objects.update_or_create(
                            uuid=row.get("uuid") or uuid.uuid4(),
                            defaults={
                                "meta_id": meta_id,
                                "data": data_aporte or timezone.localdate(),
                                "valor": DecimalAporte(str(row.get("valor") or 0)),
                                "observacao": row.get("observacao") or "",
                            },
                        )
                        total_restored += 1
                    except Exception as e:
                        logger.warning("Falha ao restaurar aporte de meta: %s", e)
                        total_ignorados += 1

            # 2c. Linhas de extrato: as antigas já sumiram em cascata com os extratos
            linhas_records = data_dict.get("data", {}).get("core", {}).get("LinhaExtrato", [])
            restauradas, ignoradas = _restaurar_linhas_extrato(linhas_records, uuid_to_id)
            total_restored += restauradas
            total_ignorados += ignoradas

            # 3. Restaurar cotações históricas se fornecidas no backup
            cotacao_records = data_dict.get("data", {}).get("investimento", {}).get("Cotacao", [])
            if cotacao_records:
                logger.debug("Restaurando %d registros de Cotacao", len(cotacao_records))
                from investimento.models import Cotacao
                from datetime import datetime
                from decimal import Decimal
                
                for row in cotacao_records:
                    ativo_uuid = row.get("ativo_uuid")
                    ativo_id = uuid_to_id.get("investimento.Ativo", {}).get(ativo_uuid)
                    if not ativo_id:
                        ativo_id = uuid_to_id.get("Ativo", {}).get(ativo_uuid)
                    
                    if ativo_id:
                        try:
                            data_str = row.get("data")
                            if data_str:
                                dt = datetime.strptime(data_str, "%Y-%m-%d").date()
                                Cotacao.objects.update_or_create(
                                    ativo_id=ativo_id,
                                    data=dt,
                                    defaults={"valor": Decimal(str(row.get("valor")))}
                                )
                        except Exception as e:
                            logger.warning("Falha ao restaurar cotação: %s", e)

            # 3b. Restaurar detalhes de Renda Fixa se fornecidos no backup
            detalhe_records = data_dict.get("data", {}).get("investimento", {}).get("DetalheRendaFixa", [])
            if detalhe_records:
                logger.debug("Restaurando %d registros de DetalheRendaFixa", len(detalhe_records))
                from investimento.models import DetalheRendaFixa
                from datetime import datetime
                from decimal import Decimal

                for row in detalhe_records:
                    ativo_uuid = row.get("ativo_uuid")
                    ativo_id = uuid_to_id.get("investimento.Ativo", {}).get(ativo_uuid)
                    if not ativo_id:
                        ativo_id = uuid_to_id.get("Ativo", {}).get(ativo_uuid)

                    if ativo_id:
                        try:
                            data_str = row.get("data_vencimento")
                            data_vencimento = (
                                datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else None
                            )
                            DetalheRendaFixa.objects.update_or_create(
                                ativo_id=ativo_id,
                                defaults={
                                    "data_vencimento": data_vencimento,
                                    "emissor": row.get("emissor") or "",
                                    "indexador": row.get("indexador") or "",
                                    "taxa": Decimal(str(row.get("taxa") or 0)),
                                }
                            )
                        except Exception as e:
                            logger.warning("Falha ao restaurar detalhe de renda fixa: %s", e)

            # 4. RECALCULAR TODOS OS ATIVOS após restauração completa das transações
            # Necessário porque os signals foram desconectados durante a importação.
            # Reconstrói também a posição por carteira, que é cache
            if ativos_restaurados:
                try:
                    from investimento.calculators import (
                        recalcular_ativo,
                        recalcular_posicoes_do_ativo,
                    )
                    for ativo in ativos_restaurados:
                        try:
                            ativo.refresh_from_db()  # Garante estado fresco do DB
                            recalcular_ativo(ativo)
                            recalcular_posicoes_do_ativo(ativo)
                        except Exception as recalc_err:
                            logger.warning(
                                "Erro ao recalcular ativo %s: %s", ativo, recalc_err
                            )
                except ImportError:
                    logger.debug("Módulo de investimentos não disponível para recálculo.")

            # 5. DEDUPLICAR FATURAS DE CARTÃO
            # Rede de segurança na fronteira do import: backups gerados por versões
            # antigas podem já conter duas faturas para o mesmo mês (uma fantasma,
            # criada pelo signal na máquina de origem). Como a restauração é fiel
            # aos dados do arquivo, a duplicidade viria junto — então normalizamos
            # aqui, ainda dentro da transação atômica.
            try:
                from core.services.fatura_service import deduplicar_faturas
                relatorio_faturas = deduplicar_faturas(usuario=user)
                faturas_removidas = sum(len(g["removidas"]) for g in relatorio_faturas)
                if faturas_removidas:
                    logger.warning(
                        "Backup continha %d fatura(s) de cartão duplicada(s); "
                        "removida(s) durante a restauração para o usuário %s.",
                        faturas_removidas, user.username,
                    )
            except Exception as e:
                logger.error("Falha ao deduplicar faturas na restauração: %s", e)
                faturas_removidas = 0

    finally:
        # ── Reconectar signals de investimento ───────────────────────────────
        if signals_disconnected:
            try:
                post_save.connect(atualizar_ativo_apos_transacao, sender=TransacaoInvestimento)
                post_delete.connect(atualizar_ativo_apos_transacao, sender=TransacaoInvestimento)
            except Exception as e:
                logger.error("Erro ao reconectar signals de investimento: %s", e)

        # ── Reconectar signals de consolidação de fatura do core ─────────────
        if core_signals_disconnected:
            try:
                post_save.connect(monitorar_salvamento_conta, sender=ContaCore)
                post_delete.connect(monitorar_delecao_conta, sender=ContaCore)
            except Exception as e:
                logger.error("Erro ao reconectar signals de fatura do core: %s", e)

    if total_ignorados:
        logger.warning(
            "Restauração concluída com %d registro(s) ignorado(s) para o usuário %s.",
            total_ignorados, user.username
        )

    msg = f"Backup restaurado com sucesso. {total_restored} registros processados."
    if total_ignorados:
        msg += f" {total_ignorados} registro(s) não puderam ser restaurados (ver logs)."
    if faturas_removidas:
        msg += (
            f" {faturas_removidas} fatura(s) de cartão duplicada(s) no backup "
            "foram consolidadas automaticamente."
        )

    return {
        "tipo": "zip",
        "msg": msg,
        "criados": total_restored,
        "atualizados": 0,
        "ignorados": total_ignorados,
        "faturas_deduplicadas": faturas_removidas,
    }


# =========================================================
# ROUTER UNIFICADO (IMPORT SERVICE)
# =========================================================



def importar_universal(arquivo, usuario, password=None) -> dict:
    """Valida o arquivo enviado e restaura o backup que ele contém.

    Não abre uma transaction.atomic() extra: o isolamento transacional e a reconexão
    dos signals ficam a cargo de `restaurar_dados_usuario`.

    Raises:
        ValueError: Se o arquivo não for um backup ZIP válido.

    Returns:
        dict: Relatório com o número de registros importados.
    """
    nome = (getattr(arquivo, "name", "") or "").lower()
    if not nome.endswith(".zip"):
        raise ValueError("Formato não suportado. Envie o backup .zip gerado pelo freecash.")

    data_dict = ler_backup_zip(arquivo, password or None)
    return restaurar_dados_usuario(data_dict, usuario)
