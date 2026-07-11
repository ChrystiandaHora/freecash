"""Serviço de Exportação Segura e Backup do Usuário.

Este módulo implementa a lógica de coleta de registros do usuário de todos os
modelos locais do projeto (multi-tenant por usuário) e executa a serialização,
derivação de chave via PBKDF2 (com Salt aleatório) e criptografia autenticada
AES-GCM para produzir o arquivo seguro de backup no formato próprio '.fcbk'.
"""

import json
import os
import base64
import hashlib
import uuid
import zlib
from decimal import Decimal
from django.utils import timezone
from django.apps import apps
from django.db.models.fields.related import ForeignKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = "4.1"


def _to_serializable(obj):
    """Converte tipos complexos do Django/Python em tipos nativos serializáveis em JSON.

    Args:
        obj (any): O valor a ser convertido (Decimal, UUID, datetime, date, etc.).

    Returns:
        any: O valor convertido em formato nativo serializável (float, str, isoformat).
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


def get_backupable_models():
    """Descobre todos os modelos locais do projeto elegíveis para backup.

    Analisa os modelos registrados no Django e filtra apenas aqueles que possuem os
    campos 'usuario' (para isolamento) e 'uuid' (para integridade de chaves estrangeiras).
    Ordena-os de acordo com a ordem correta de dependência relacional.

    Returns:
        list[Model]: Lista ordenada de classes de Modelos elegíveis para backup.
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
        "ReceitaRecorrente": 7.5,
        "Conta": 8,
        "Transacao": 9,
        "CarteiraHistorico": 10,
    }

    def get_priority(m):
        return priority.get(m.__name__, 100)

    return sorted(backup_models, key=get_priority)


def encrypt_data(data_dict, password):
    """Criptografa um dicionário Python usando criptografia autenticada AES-GCM.

    Aplica derivação de chave robusta PBKDF2-HMAC-SHA256, gerando um Salt aleatório
    e executando a cifra AES-GCM com um Nonce seguro. Garante também checagem de
    integridade pública injetando o hash SHA256 do payload criptografado.

    Args:
        data_dict (dict): Dicionário contendo os metadados e dados exportados.
        password (str): Senha definida pelo usuário para o backup.

    Returns:
        str: String codificada em Base64 contendo os dados protegidos (arquivo .fcbk).
    """
    json_data = json.dumps(data_dict, default=_to_serializable).encode("utf-8")
    compressed_data = zlib.compress(json_data, level=6)
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
    ciphertext = aesgcm.encrypt(nonce, compressed_data, None)

    # Payload format: SALT(16) + NONCE(12) + CIPHERTEXT
    payload = salt + nonce + ciphertext

    # Integrity Check: SHA256(Payload) + Payload
    public_hash = hashlib.sha256(payload).digest()
    final_file_data = public_hash + payload

    return base64.b64encode(final_file_data).decode("utf-8")


def export_user_data(user, password):
    """Coleta e exporta todos os registros financeiros do usuário em formato criptografado.

    Varre todos os modelos locais relevantes, mapeia e resolve relacionamentos
    baseando-se em UUIDs seguros (para preservação ao restaurar em outros bancos),
    e aplica a criptografia simétrica com a senha fornecida.

    Args:
        user (User): O usuário Django proprietário das informações.
        password (str): Senha de proteção do backup.

    Returns:
        str: O conteúdo do backup final criptografado em Base64.
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

        fk_names = [
            f.name
            for f in model._meta.fields
            if isinstance(f, ForeignKey) and f.name != "usuario"
        ]
        queryset = model.objects.filter(usuario=user)
        if fk_names:
            queryset = queryset.select_related(*fk_names)

        records = []
        for obj in queryset.iterator(chunk_size=1000):
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

    # Exportar Cotacao e DetalheRendaFixa manualmente, pois não possuem usuario diretamente
    from investimento.models import Ativo, Cotacao, DetalheRendaFixa
    ativos_usuario_ids = Ativo.objects.filter(usuario=user).values_list("id", flat=True)

    detalhes_qs = DetalheRendaFixa.objects.filter(ativo_id__in=ativos_usuario_ids).select_related("ativo")
    detalhes_records = []
    for obj in detalhes_qs.iterator(chunk_size=1000):
        detalhes_records.append({
            "ativo_uuid": str(obj.ativo.uuid),
            "data_vencimento": obj.data_vencimento.isoformat() if obj.data_vencimento else None,
            "emissor": obj.emissor,
            "indexador": obj.indexador,
            "taxa": float(obj.taxa),
        })

    if "investimento" not in data["data"]:
        data["data"]["investimento"] = {}
    data["data"]["investimento"]["DetalheRendaFixa"] = detalhes_records

    cotacoes_qs = Cotacao.objects.filter(ativo_id__in=ativos_usuario_ids).select_related("ativo")

    cotacoes_records = []
    for obj in cotacoes_qs.iterator(chunk_size=1000):
        row = {
            "ativo_uuid": str(obj.ativo.uuid),
            "data": obj.data.isoformat() if hasattr(obj.data, "isoformat") else str(obj.data),
            "valor": float(obj.valor),
        }
        cotacoes_records.append(row)
        
    if "investimento" not in data["data"]:
        data["data"]["investimento"] = {}
    data["data"]["investimento"]["Cotacao"] = cotacoes_records

    return encrypt_data(data, password)


