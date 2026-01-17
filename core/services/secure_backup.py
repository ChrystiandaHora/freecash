import json
import os
import base64
import hashlib
import uuid
from decimal import Decimal
from django.utils import timezone
from django.apps import apps
from django.db import transaction
from django.db.models.fields.related import ForeignKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecureBackupService:
    VERSION = "4.0"  # Dynamic Modular Format

    @staticmethod
    def _to_serializable(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return obj

    @classmethod
    def get_backupable_models(cls):
        """
        Descobre todos os modelos do projeto que possuem o campo 'usuario' e o campo 'uuid'.
        Filtra apenas apps locais do projeto (evita apps de terceiros).
        Retorna uma lista ordenada por dependência básica.
        """
        from django.conf import settings

        project_root = str(settings.BASE_DIR)
        backup_models = []

        for app_config in apps.get_app_configs():
            # Verifica se o app é local (está dentro do diretório do projeto)
            # E não é um app de sistema/contas padrão
            app_path = os.path.abspath(app_config.path)
            if app_path.startswith(os.path.abspath(project_root)):
                for model in app_config.get_models():
                    # Deve ter usuario e uuid (AuditoriaModel)
                    fields = [f.name for f in model._meta.get_fields()]
                    if "usuario" in fields and "uuid" in fields:
                        backup_models.append(model)

        # Ordem de prioridade manual para garantir integridade referencial básica
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

    @classmethod
    def gather_user_data(cls, user):
        """
        Coleta dinamicamente os dados de todos os modelos registrados.
        Para ForeignKeys, salva o UUID do objeto relacionado em vez do ID local.
        """
        models_to_backup = cls.get_backupable_models()
        data = {
            "metadata": {
                "version": cls.VERSION,
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

        return data

    @classmethod
    def encrypt_data(cls, data_dict, password):
        """
        Criptografa com HASH + AES-GCM.
        """
        json_data = json.dumps(data_dict, default=cls._to_serializable).encode("utf-8")
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
        payload = salt + nonce + ciphertext
        public_hash = hashlib.sha256(payload).digest()
        final_file_data = public_hash + payload
        return base64.b64encode(final_file_data).decode("utf-8")

    @classmethod
    def decrypt_data(cls, encrypted_base64, password):
        """
        Descriptografa e valida integridade.
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

    @classmethod
    def restore_user_data(cls, data_dict, user):
        """
        Restaura dinamicamente, SUBSTITUINDO todos os dados do usuário.
        Primeiro apaga todos os dados existentes, depois importa o backup.
        """
        from django.db.models import OneToOneField

        backup_models = cls.get_backupable_models()

        # Mapa: { ModelName: { uuid_str: local_id } }
        uuid_to_id = {}

        total_restored = 0

        with transaction.atomic():
            # PASSO 1: Apagar todos os dados existentes do usuário
            # Deleta em ordem reversa para respeitar ForeignKeys
            for model in reversed(backup_models):
                # Para OneToOne (ConfigUsuario), não deletamos, apenas limparemos depois
                is_one_to_one = False
                for field in model._meta.fields:
                    if isinstance(field, OneToOneField) and field.name == "usuario":
                        is_one_to_one = True
                        break

                if not is_one_to_one:
                    model.objects.filter(usuario=user).delete()

            # Inicializa mapa vazio (dados foram apagados)
            for model in backup_models:
                uuid_to_id[model.__name__] = {}

            # PASSO 2: Importar todos os dados do backup
            for model in backup_models:
                app_label = model._meta.app_label
                model_name = model.__name__

                # Detecta se é um modelo com OneToOneField para User
                is_one_to_one_user = False
                for field in model._meta.fields:
                    if isinstance(field, OneToOneField) and field.name == "usuario":
                        is_one_to_one_user = True
                        break

                records = (
                    data_dict.get("data", {}).get(app_label, {}).get(model_name, [])
                )
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
                                # Tenta encontrar o ID local para esse UUID
                                target_model_name = field.remote_field.model.__name__
                                local_fk_id = uuid_to_id.get(target_model_name, {}).get(
                                    str(val_uuid)
                                )
                                row[f"{field.name}_id"] = local_fk_id
                            else:
                                row[f"{field.name}_id"] = None

                    # Upsert com tratamento de conflitos
                    try:
                        if is_one_to_one_user:
                            # Para OneToOne, usamos usuario como chave única
                            obj, created = model.objects.update_or_create(
                                usuario=user, defaults=row
                            )
                        else:
                            # Para outros modelos, usa uuid como chave
                            obj, created = model.objects.update_or_create(
                                uuid=uid, usuario=user, defaults=row
                            )
                    except Exception:
                        # Fallback: tenta encontrar por nome (natural key) se existir
                        nome = row.get("nome")
                        if nome:
                            existing = model.objects.filter(
                                usuario=user, nome=nome
                            ).first()
                            if existing:
                                for key, value in row.items():
                                    setattr(existing, key, value)
                                existing.save()
                                obj = existing
                            else:
                                # Se não encontrou por nome, gera novo UUID
                                row["uuid"] = uuid.uuid4()
                                obj = model.objects.create(usuario=user, **row)
                        else:
                            # Sem nome, gera novo UUID e tenta criar
                            row["uuid"] = uuid.uuid4()
                            obj = model.objects.create(usuario=user, **row)

                    uuid_to_id[model_name][str(uid)] = obj.id
                    total_restored += 1

        return {"total": total_restored}
