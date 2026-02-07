import json
import os
import base64
import hashlib
import uuid
from decimal import Decimal
from django.utils import timezone
from django.apps import apps
from django.db.models.fields.related import ForeignKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# =========================================================
# EXPORT SERVICE (Secure JSON Backup)
# =========================================================

VERSION = "4.0"


def _to_serializable(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


def get_backupable_models():
    """
    Descobre todos os modelos do projeto que possuem o campo 'usuario' e o campo 'uuid'.
    Filtra apenas apps locais do projeto.
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
        "FormaPagamento": 3,
        "CartaoCredito": 4,
        "ClasseAtivo": 5,
        "CategoriaAtivo": 6,
        "SubcategoriaAtivo": 7,
        "Ativo": 8,
        "Assinatura": 9,
        "Conta": 10,
        "Transacao": 11,
    }

    def get_priority(m):
        return priority.get(m.__name__, 100)

    return sorted(backup_models, key=get_priority)


def encrypt_data(data_dict, password):
    """
    Criptografa com HASH + AES-GCM.
    """
    json_data = json.dumps(data_dict, default=_to_serializable).encode("utf-8")
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, json_data, None)

    # Payload format: SALT(16) + NONCE(12) + CIPHERTEXT
    payload = salt + nonce + ciphertext

    # Integrity Check: SHA256(Payload) + Payload
    public_hash = hashlib.sha256(payload).digest()
    final_file_data = public_hash + payload

    return base64.b64encode(final_file_data).decode("utf-8")


def export_user_data(user, password):
    """
    Coleta os dados do usuário e retorna a string criptografada (.fcbk content).
    """
    models_to_backup = get_backupable_models()
    data = {
        "metadata": {
            "version": VERSION,
            "generated_at": timezone.now().isoformat(),
            "username": user.username,
        },
        "data": {},
    }

    for model in models_to_backup:
        app_label = model._meta.app_label
        model_name = model.__name__

        if app_label not in data["data"]:
            data["data"][app_label] = {}

        records = []
        for obj in model.objects.filter(usuario=user):
            row = {}
            for field in model._meta.fields:
                if field.name in ["id", "usuario"]:
                    continue

                if isinstance(field, ForeignKey):
                    related_obj = getattr(obj, field.name)
                    if related_obj and hasattr(related_obj, "uuid"):
                        row[f"{field.name}_uuid"] = str(related_obj.uuid)
                    else:
                        row[f"{field.name}_uuid"] = None
                else:
                    row[field.name] = getattr(obj, field.name)
            records.append(row)

        data["data"][app_label][model_name] = records

    return encrypt_data(data, password)
