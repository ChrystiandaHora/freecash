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
import zlib
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from django.db.models.fields.related import ForeignKey, OneToOneField
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = {"4.0", "4.1"}


# =========================================================
# LÓGICA SECURE IMPORT (JSON / .FCBK)
# =========================================================


def decrypt_data_fcbk(encrypted_base64: str, password: str) -> dict:
    """Descriptografa arquivos de backup no formato '.fcbk' utilizando senha e PBKDF2.

    Realiza a validação do hash SHA256 no início do arquivo para detectar violações,
    extrai os blocos de Salt/Nonce e descriptografa via AES-GCM, convertendo o
    JSON resultante em dicionário estruturado.

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
        try:
            decrypted_data = zlib.decompress(decrypted_data)
        except zlib.error:
            pass  # backup gerado antes da versão 4.1, sem compressão

        data_dict = json.loads(decrypted_data.decode("utf-8"))
    except Exception as e:
        if "VIOLADO" in str(e):
            raise e
        raise ValueError("Senha incorreta ou arquivo corrompido.")

    version = data_dict.get("metadata", {}).get("version")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Versão de backup não suportada: {version!r}. "
            f"Versões aceitas: {sorted(SUPPORTED_VERSIONS)}."
        )
    return data_dict


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
        "PlanoMetas": 1.5,
        "Categoria": 2,
        "CartaoCredito": 3,
        "ClasseAtivo": 4,
        "CategoriaAtivo": 5,
        "SubcategoriaAtivo": 6,
        # A carteira precede o ativo porque transações e posições apontam para ela.
        "Carteira": 6.5,
        "Ativo": 7,
        "LancamentoRecorrente": 7.5,
        "Conta": 8,
        "Transacao": 9,
        "PosicaoCarteira": 9.5,
        "CarteiraHistorico": 10,
        # MetaFinanceira não referencia outros modelos; os aportes dependem dela
        # e são restaurados à parte, por não terem FK direta para o usuário.
        "MetaFinanceira": 11,
    }

    def get_priority(m):
        return priority.get(m.__name__, 100)

    return sorted(backup_models, key=get_priority)


# Nomes de classe usados em versões anteriores do sistema, por modelo atual.
# As chaves do arquivo `.fcbk` são nomes de classe, então renomear um modelo
# invalidaria os backups já gerados pelos usuários.
NOMES_LEGADOS_DE_MODELO = {
    "LancamentoRecorrente": ("ReceitaRecorrente",),
}

# Renomeações de campo, por modelo atual: {nome_antigo: nome_novo}. Chaves de
# chave estrangeira aparecem no backup como `<campo>_uuid`.
CAMPOS_RENOMEADOS_POR_MODELO = {
    "Conta": {"receita_recorrente_uuid": "recorrencia_uuid"},
}

# Campos que mudaram de modelo. `filter_valid_fields` descarta o que não existe mais,
# então sem isto a meta de alocação de um `.fcbk` anterior às carteiras some calada e o
# balanceamento volta com tudo em 0% (ver docs/backup.md).
CAMPOS_MOVIDOS_DE_MODELO = {
    "Ativo": {"meta_porcentagem": "PosicaoCarteira"},
}

# FKs que viraram obrigatórias depois do backup existir. Sem isto, restaurar um
# `.fcbk` anterior às carteiras descarta as transações em silêncio (ver docs/carteiras.md).
FKS_LEGADAS_COM_PADRAO = {
    "Transacao": ("carteira",),
    "CarteiraHistorico": ("carteira",),
    "PosicaoCarteira": ("carteira",),
}


def _carteira_padrao(user):
    """Devolve (criando se preciso) a carteira que recebe dados de backups antigos.

    Returns:
        Carteira: A primeira carteira do usuário, ou uma Carteira Padrão nova.
    """
    from investimento.models import Carteira

    return Carteira.padrao_de(user)


def _normalizar_campos_legados(model_name: str, linha: dict) -> dict:
    """Reescreve as chaves de um registro de backup para os nomes atuais.

    Returns:
        dict: O mesmo registro, com as chaves renomeadas quando aplicável.
    """
    renomeios = CAMPOS_RENOMEADOS_POR_MODELO.get(model_name)
    if not renomeios:
        return linha

    for antigo, novo in renomeios.items():
        if antigo in linha and novo not in linha:
            linha[novo] = linha.pop(antigo)
    return linha


def restore_user_data_fcbk(data_dict: dict, user) -> dict:
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
    # {ativo_id: meta} lida do `Ativo` de backups anteriores às carteiras
    metas_legadas_por_ativo: dict[int, str] = {}

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

            # Resolvido uma vez só, e apenas se algum registro legado precisar dele.
            carteira_padrao_cache: dict[str, int] = {}

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

                # Compatibilidade com backups gerados antes de um modelo ser
                # renomeado. As chaves do `.fcbk` são nomes de classe, então um
                # rename tornaria os registros invisíveis aqui e a restauração
                # perderia os dados em silêncio — sem erro algum, que é o pior tipo
                # de falha num backup.
                if not records:
                    for nome_legado in NOMES_LEGADOS_DE_MODELO.get(model_name, ()):
                        legados = registros_do_app.get(nome_legado)
                        if legados:
                            logger.info(
                                "Backup antigo: lendo %s a partir da chave legada %s.",
                                model_name, nome_legado,
                            )
                            records = legados
                            break

                # A normalização de campo vale para TODO registro, não só para os de
                # chave legada: `Conta` nunca foi renomeada, mas o campo que aponta
                # para a regra de recorrência foi (`receita_recorrente` ->
                # `recorrencia`), e as FKs aparecem no backup como `<campo>_uuid`.
                # Sem isto, restaurar um backup antigo devolveria as contas sem o
                # vínculo com a regra que as gerou.
                if records and model_name in CAMPOS_RENOMEADOS_POR_MODELO:
                    records = [
                        _normalizar_campos_legados(model_name, dict(linha))
                        for linha in records
                    ]
                logger.debug(
                    "Restaurando %d registros de %s.%s", len(records), app_label, model_name
                )

                for row in records:
                    uid = row.pop("uuid", None)
                    if not uid:
                        total_ignorados += 1
                        continue

                    # Guardado antes da filtragem: o campo não existe mais neste modelo
                    meta_legada = None
                    if model_name in CAMPOS_MOVIDOS_DE_MODELO:
                        for campo in CAMPOS_MOVIDOS_DE_MODELO[model_name]:
                            if row.get(campo) is not None:
                                meta_legada = row[campo]

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

                    # Backup antigo não traz `carteira_uuid`; sem o padrão, o NOT NULL descarta a ordem
                    for campo in FKS_LEGADAS_COM_PADRAO.get(model_name, ()):
                        if row.get(f"{campo}_id") is None:
                            if "id" not in carteira_padrao_cache:
                                carteira_padrao_cache["id"] = _carteira_padrao(user).id
                            row[f"{campo}_id"] = carteira_padrao_cache["id"]

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
                            total_ignorados += 1
                            continue

                    if obj is not None:
                        uuid_to_id[composite_key][str(uid)] = obj.id
                        uuid_to_id[model_name][str(uid)] = obj.id
                        total_restored += 1

                        # Rastrear ativos restaurados para recálculo posterior
                        if model_name == "Ativo":
                            ativos_restaurados.append(obj)
                            if meta_legada is not None:
                                metas_legadas_por_ativo[obj.id] = meta_legada

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
            # Reconstrói também a posição por carteira: é cache, e o backup antigo nem a tem
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

            # 4b. Reconduzir a meta de alocação que vinha no `Ativo`
            # Só entra em backup anterior às carteiras: o export atual grava a meta na
            # `PosicaoCarteira`, e aí o laço acima já a restaurou. Roda depois do
            # recálculo porque é ele que cria as posições que recebem o valor.
            if metas_legadas_por_ativo:
                from decimal import Decimal as DecimalMeta

                from investimento.models import PosicaoCarteira

                recuperadas = 0
                for ativo_id, meta in metas_legadas_por_ativo.items():
                    posicoes = list(
                        PosicaoCarteira.objects.filter(usuario=user, ativo_id=ativo_id)
                    )
                    # A meta era global por ativo; dividi-la entre custódias exigiria um
                    # critério que o arquivo não tem. Com uma posição só não há dúvida.
                    if len(posicoes) != 1:
                        if len(posicoes) > 1:
                            logger.warning(
                                "Meta legada do ativo %s não aplicada: %d posições, "
                                "e o backup não diz como dividir entre elas.",
                                ativo_id, len(posicoes),
                            )
                        continue
                    try:
                        PosicaoCarteira.objects.filter(pk=posicoes[0].pk).update(
                            meta_porcentagem=DecimalMeta(str(meta))
                        )
                        recuperadas += 1
                    except (ArithmeticError, TypeError, ValueError) as meta_err:
                        logger.warning(
                            "Meta legada inválida no ativo %s (%r): %s",
                            ativo_id, meta, meta_err,
                        )
                if recuperadas:
                    logger.info(
                        "Backup anterior às carteiras: %d meta(s) de alocação movida(s) "
                        "do ativo para a posição na carteira.", recuperadas,
                    )

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
        "tipo": "fcbk",
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
    """Função controladora principal que valida e roteia a importação do arquivo.

    Aceita apenas arquivos sob extensão '.fcbk' criptografados para restaurar a
    base de dados de forma segura. Não adiciona uma transaction.atomic() extra —
    o isolamento transacional é gerenciado internamente por
    `restore_user_data_fcbk`, que também garante a reconexão dos signals Django
    de investimentos via bloco `try/finally` ao redor da transaction.

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
