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
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from django.db.models.fields.related import ForeignKey, OneToOneField
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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
    }

    def get_priority(m):
        return priority.get(m.__name__, 100)

    return sorted(backup_models, key=get_priority)


def restore_user_data_fcbk(data_dict: dict, user) -> dict:
    """Substitui transacionalmente todas as entidades do usuário com os dados do backup.

    Executa um processo atômico de limpeza (delete) dos dados atuais do usuário e
    insere as novas entidades mapeando e religando chaves estrangeiras com base
    em UUIDs estáveis contidos no dicionário de backup.

    Args:
        data_dict (dict): Dicionário contendo os dados decodificados do backup.
        user (User): O usuário Django que está restaurando a base de dados.

    Returns:
        dict: Estatísticas contendo total de registros restaurados ou falhas.
    """
    backup_models = get_backupable_models()
    uuid_to_id = {}
    total_restored = 0

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

    with transaction.atomic():
        # 1. DELETE EXISTING
        for model in reversed(backup_models):
            is_one_to_one = False
            for field in model._meta.fields:
                if isinstance(field, OneToOneField) and field.name == "usuario":
                    is_one_to_one = True
                    break

            if not is_one_to_one:
                model.objects.filter(usuario=user).delete()

        for model in backup_models:
            uuid_to_id[model.__name__] = {}

        # 2. IMPORT NEW
        for model in backup_models:
            app_label = model._meta.app_label
            model_name = model.__name__

            is_one_to_one_user = False
            for field in model._meta.fields:
                if isinstance(field, OneToOneField) and field.name == "usuario":
                    is_one_to_one_user = True
                    break

            records = data_dict.get("data", {}).get(app_label, {}).get(model_name, [])

            for row in records:
                uid = row.pop("uuid", None)
                if not uid:
                    continue

                # Resolve FKs
                for field in model._meta.fields:
                    if isinstance(field, ForeignKey) and field.name != "usuario":
                        fk_uuid_key = f"{field.name}_uuid"
                        val_uuid = row.pop(fk_uuid_key, None)

                        if val_uuid:
                            target_name = field.remote_field.model.__name__
                            local_id = uuid_to_id.get(target_name, {}).get(
                                str(val_uuid)
                            )
                            row[f"{field.name}_id"] = local_id
                        else:
                            row[f"{field.name}_id"] = None

                # Filtrar campos que não existem mais no modelo
                row = filter_valid_fields(model, row)

                # Upsert/Create
                try:
                    if is_one_to_one_user:
                        obj, created = model.objects.update_or_create(
                            usuario=user, defaults=row
                        )
                    else:
                        obj, created = model.objects.update_or_create(
                            uuid=uid, usuario=user, defaults=row
                        )
                except Exception:
                    # Fallback (Name matching)
                    nome = row.get("nome")
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

                uuid_to_id[model_name][str(uid)] = obj.id
                total_restored += 1

    return {
        "tipo": "fcbk",
        "msg": f"Backup restaurado. {total_restored} registros.",
        "criados": total_restored,
        "atualizados": 0,
        "ignorados": 0,
    }


# =========================================================
# ROUTER UNIFICADO (IMPORT SERVICE)
# =========================================================


@transaction.atomic
def importar_universal(arquivo, usuario, password=None) -> dict:
    """Função controladora principal que valida e roteia a importação do arquivo.

    Aceita apenas arquivos sob extensão '.fcbk' criptografados para restaurar a
    base de dados de forma segura.

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
