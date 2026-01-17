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

from core.models import LogImportacao

# =========================================================
# LÓGICA SECURE IMPORT (JSON / .FCBK)
# =========================================================


def decrypt_data_fcbk(encrypted_base64, password):
    """
    Descriptografa arquivo .fcbk (JSON + AES-GCM).
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
    """Mesma lógica do export para descobrir ordem de restore."""
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
        "FormaPagamento": 3,
        "ClasseAtivo": 5,
        "CategoriaAtivo": 6,
        "SubcategoriaAtivo": 7,
        "Ativo": 8,
        "Conta": 9,
        "Transacao": 10,
    }

    def get_priority(m):
        return priority.get(m.__name__, 100)

    return sorted(backup_models, key=get_priority)


def restore_user_data_fcbk(data_dict, user):
    """
    Restaura dados JSON (.fcbk). SUBSTITUI DADOS EXISTENTES.
    """
    backup_models = get_backupable_models()
    uuid_to_id = {}
    total_restored = 0

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

    return {"tipo": "fcbk", "msg": f"Backup restaurado. {total_restored} registros."}


# =========================================================
# ROUTER UNIFICADO (IMPORT SERVICE)
# =========================================================


@transaction.atomic
def importar_universal(arquivo, usuario, password=None):
    """
    Função principal que aceita APENAS arquivos .fcbk (JSON criptografado).
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
