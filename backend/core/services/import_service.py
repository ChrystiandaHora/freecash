"""Serviço de Descriptografia e Restauração de Backups (.fcbk Importer).

Este módulo processa arquivos de backup importados no formato '.fcbk', realizando a
autenticação da senha via derivação de chaves PBKDF2, descriptografia simétrica
AES-GCM, verificação de integridade digital SHA256 e gravação transacional atômica
de todas as entidades financeiras na base PostgreSQL (multi-tenant por usuário).
"""

from __future__ import annotations

import json
import os
import base64
import hashlib
import uuid
import io
import logging
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from django.db.models.fields.related import ForeignKey, OneToOneField
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


# =========================================================
# LÓGICA SECURE IMPORT (JSON / .FCBK)
# =========================================================


def decrypt_data_fcbk(encrypted_base64: str, password: str) -> dict:
    """Descriptografa arquivos de backup no formato '.fcbk' utilizando senha e PBKDF2.

    Realiza a validação do hash SHA256 no início do arquivo para detectar violações,
    extrai os blocos de Salt/Nonce e descriptografa via AES-GCM, convertendo o
    JSON resultante em dicionário estruturado.

    Args:
        encrypted_base64 (str): O conteúdo codificado em Base64 lido do arquivo.
        password (str): Senha do backup definida pelo usuário.

    Raises:
        ValueError: Se o arquivo estiver violado, senha incorreta ou arquivo corrompido.

    Returns:
        dict: O dicionário de metadados e registros decodificados.
    """
    try:
        raw_data = base64.b64decode(encrypted_base64)
        stored_hash = raw_data[:32]
        payload = raw_data[32:]

        if hashlib.sha256(payload).digest() != stored_hash:
            raise ValueError("O arquivo foi VIOLADO.")

        salt = payload[:16]
        nonce = payload[16:28]
        ciphertext = payload[28:]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000
        )
        key = kdf.derive(password.encode("utf-8"))

        aesgcm = AESGCM(key)
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(decrypted_data.decode("utf-8"))
    except Exception as e:
        if "VIOLADO" in str(e):
            raise e
        raise ValueError("Senha incorreta ou arquivo corrompido.")


def get_backupable_models():
    """Descobre e ordena todos os modelos locais elegíveis para restauração.

    Garante que os dados sejam restaurados na ordem correta de dependência de chaves
    estrangeiras, prevenindo falhas de integridade referencial.

    Returns:
        list[Model]: Lista de classes de Modelos Django elegíveis para restore.
    """
    from django.conf import settings

    project_root = str(settings.BASE_DIR)
    backup_models = []

    for app_config in apps.get_app_configs():
        app_path = os.path.abspath(app_config.path)
        if app_path.startswith(os.path.abspath(project_root)):
            for model in app_config.get_models():
                fields = [f.name for f in model._meta.get_fields()]
                if "usuario" in fields and "uuid" in fields:
                    backup_models.append(model)

    priority = {
        "ConfigUsuario": 1,
        "Categoria": 2,
        "CartaoCredito": 3,
        "ClasseAtivo": 4,
        "CategoriaAtivo": 5,
        "SubcategoriaAtivo": 6,
        "Ativo": 7,
        "Conta": 8,
        "Transacao": 9,
        "CarteiraHistorico": 10,
    }

    def get_priority(m):
        return priority.get(m.__name__, 100)

    return sorted(backup_models, key=get_priority)


def restore_user_data_fcbk(data_dict: dict, user) -> dict:
    """Substitui transacionalmente todas as entidades do usuário com os dados do backup.

    Executa um processo atômico de limpeza (delete) dos dados atuais do usuário e
    insere as novas entidades mapeando e religando chaves estrangeiras com base
    em UUIDs estáveis contidos no dicionário de backup.

    Desconecta temporariamente os signals do módulo de investimentos durante a
    restauração para evitar recálculos parciais e incorretos de preço médio e
    quantidade dos ativos enquanto as transações são reinseridas individualmente.
    Após a restauração completa, força o recálculo de todos os ativos afetados.

    Args:
        data_dict (dict): Dicionário contendo os dados decodificados do backup.
        user (User): O usuário Django que está restaurando a base de dados.

    Returns:
        dict: Estatísticas contendo total de registros restaurados ou falhas.
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

    backup_models = get_backupable_models()
    uuid_to_id = {}
    total_restored = 0
    ativos_restaurados = []  # rastreia ativos para recálculo posterior

    def get_model_field_names(model):
        """Retorna os nomes de campos válidos do modelo."""
        return {
            f.name
            for f in model._meta.get_fields()
            if hasattr(f, "column") or f.name in ["id"]
        }

    def filter_valid_fields(model, row):
        """Filtra apenas campos que existem no modelo atual."""
        valid_fields = get_model_field_names(model)
        # Também incluir campos de FK com sufixo _id
        valid_fk_fields = {
            f"{f.name}_id" for f in model._meta.fields if isinstance(f, ForeignKey)
        }
        all_valid = valid_fields | valid_fk_fields
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

                records = data_dict.get("data", {}).get(app_label, {}).get(model_name, [])
                logger.debug(
                    "Restaurando %d registros de %s.%s", len(records), app_label, model_name
                )

                for row in records:
                    uid = row.pop("uuid", None)
                    if not uid:
                        continue

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
                            continue

                    if obj is not None:
                        uuid_to_id[composite_key][str(uid)] = obj.id
                        uuid_to_id[model_name][str(uid)] = obj.id
                        total_restored += 1

                        # Rastrear ativos restaurados para recálculo posterior
                        if model_name == "Ativo":
                            ativos_restaurados.append(obj)

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

            # 4. RECALCULAR TODOS OS ATIVOS após restauração completa das transações
            # Necessário porque os signals foram desconectados durante a importação.
            if ativos_restaurados:
                try:
                    from investimento.calculators import recalcular_ativo
                    for ativo in ativos_restaurados:
                        try:
                            ativo.refresh_from_db()  # Garante estado fresco do DB
                            recalcular_ativo(ativo)
                        except Exception as recalc_err:
                            logger.warning(
                                "Erro ao recalcular ativo %s: %s", ativo, recalc_err
                            )
                except ImportError:
                    logger.debug("Módulo de investimentos não disponível para recálculo.")

    finally:
        # ── Reconectar signals de investimento ───────────────────────────────
        if signals_disconnected:
            try:
                post_save.connect(atualizar_ativo_apos_transacao, sender=TransacaoInvestimento)
                post_delete.connect(atualizar_ativo_apos_transacao, sender=TransacaoInvestimento)
            except Exception as e:
                logger.error("Erro ao reconectar signals de investimento: %s", e)

    return {
        "tipo": "fcbk",
        "msg": f"Backup restaurado com sucesso. {total_restored} registros processados.",
        "criados": total_restored,
        "atualizados": 0,
        "ignorados": 0,
    }


# =========================================================
# ROUTER UNIFICADO (IMPORT SERVICE)
# =========================================================



def importar_universal(arquivo, usuario, password=None) -> dict:
    """Função controladora principal que valida e roteia a importação do arquivo.

    Aceita apenas arquivos sob extensão '.fcbk' criptografados para restaurar a
    base de dados de forma segura. Não adiciona uma transaction.atomic() extra —
    o isolamento transacional é gerenciado internamente por
    `restore_user_data_fcbk`, que também garante a reconexão dos signals Django
    de investimentos via bloco `try/finally` ao redor da transaction.

    Args:
        arquivo (File): O arquivo binário do backup carregado.
        usuario (User): Instância do usuário que está processando o backup.
        password (str, optional): Senha de criptografia. Requerido para '.fcbk'.

    Raises:
        ValueError: Se o formato for inválido ou a senha estiver faltando.

    Returns:
        dict: Relatório descritivo com o número de registros importados.
    """
    nome = (getattr(arquivo, "name", "") or "").lower()

    if nome.endswith(".fcbk"):
        if not password:
            raise ValueError("Senha obrigatória para arquivo .fcbk.")

        content = arquivo.read() if hasattr(arquivo, "read") else arquivo
        data_dict = decrypt_data_fcbk(content, password)
        return restore_user_data_fcbk(data_dict, usuario)

    # Rejeita qualquer outro formato
    raise ValueError("Formato não suportado. Utilize apenas arquivos de backup .fcbk")
