import re
import calendar
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd

from django.db import transaction
from django.utils import timezone

from core.models import Conta, FormaPagamento, Categoria


MESES_MAP = {
    "JANEIRO": 1,
    "FEVEREIRO": 2,
    "MARÇO": 3,
    "MARCO": 3,
    "ABRIL": 4,
    "MAIO": 5,
    "JUNHO": 6,
    "JULHO": 7,
    "AGOSTO": 8,
    "SETEMBRO": 9,
    "OUTUBRO": 10,
    "NOVEMBRO": 11,
    "DEZEMBRO": 12,
}

SECOES = {"FIXOS EU", "FIXOS CASA", "CARTAO"}
IGNORAR_LINHAS = {"SUB-TOTAL", "TOTAL", "", None}

# ---- Formas padrão (padronização do legado) ----
FP_PIX = "PIX"
FP_BOLETO = "Boleto"
FP_CREDITO = "Cartão de Crédito"
FP_DEBITO = "Cartão de Débito"


def get_or_create_formas_padrao(usuario):
    """
    Garante que existam as 4 formas padrões.
    Retorna dict com os objetos.
    """
    formas = {}
    for nome in [FP_PIX, FP_BOLETO, FP_CREDITO, FP_DEBITO]:
        obj, _ = FormaPagamento.objects.get_or_create(
            created_by=usuario,
            nome=nome,
            defaults={"ativa": True},
        )
        if not obj.ativa:
            obj.ativa = True
            obj.save(update_fields=["ativa"])
        formas[nome] = obj
    return formas


def inferir_forma_pagamento(desc: str, secao: str, is_receita: bool, formas_padrao):
    """
    Decide a forma de pagamento baseada em:
    - secao do excel
    - palavras-chave no texto
    - fallback diferente para receita vs conta
    """
    texto = (desc or "").strip().upper()
    sec = (secao or "").strip().upper()

    # regra forte pela seção
    if sec == "CARTAO":
        return formas_padrao[FP_CREDITO]

    # palavras-chave no texto
    if "PIX" in texto:
        return formas_padrao[FP_PIX]
    if "BOLETO" in texto:
        return formas_padrao[FP_BOLETO]
    if "DEBITO" in texto or "DÉBITO" in texto:
        return formas_padrao[FP_DEBITO]
    if "CREDITO" in texto or "CRÉDITO" in texto:
        return formas_padrao[FP_CREDITO]

    # fallback
    if is_receita:
        return formas_padrao[FP_PIX]
    return formas_padrao[FP_BOLETO]


# ---- helpers de parsing ----
def parse_brl(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        if pd.isna(value):
            return Decimal("0")
    except Exception:
        pass

    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    s = str(value).strip()
    if not s:
        return Decimal("0")

    s = s.replace("R$", "").strip()
    s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^0-9\.\-]", "", s)

    if s in {"", ".", "-"}:
        return Decimal("0")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def detectar_header_meses(row_values) -> dict[int, int]:
    col_map = {}
    for idx, cell in enumerate(row_values):
        if cell is None:
            continue
        nome = str(cell).strip().upper()
        if nome in MESES_MAP:
            col_map[idx] = MESES_MAP[nome]
    return col_map if len(col_map) >= 6 else {}


def extrair_dia_vencimento(texto: str) -> int | None:
    if not texto:
        return None
    m = re.search(r"\bd\s*/\s*(\d{1,2})\b", texto, flags=re.IGNORECASE)
    if not m:
        return None
    d = int(m.group(1))
    return d if 1 <= d <= 31 else None


def limpar_descricao(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(
        r"\s*\bd\s*/\s*\d{1,2}\b", "", str(texto), flags=re.IGNORECASE
    ).strip()


def ajustar_dia(ano: int, mes: int, dia: int) -> int:
    ultimo = calendar.monthrange(ano, mes)[1]
    return min(max(dia, 1), ultimo)


def is_dia_util(d: date) -> bool:
    # segunda=0 ... domingo=6
    return d.weekday() < 5


def quinto_dia_util(ano: int, mes: int) -> date:
    """
    Retorna o 5º dia útil (considera apenas fim de semana; não considera feriados).
    """
    count = 0
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        dt = date(ano, mes, dia)
        if is_dia_util(dt):
            count += 1
            if count == 5:
                return dt
    # fallback improvável
    return date(ano, mes, 1)


# ---- categorias padrão ----
def get_or_create_categorias_padrao(usuario):
    cat_receita, _ = Categoria.objects.get_or_create(
        created_by=usuario,
        nome="Receita",
        defaults={"tipo": Categoria.TIPO_RECEITA, "is_default": True},
    )
    cat_gastos, _ = Categoria.objects.get_or_create(
        created_by=usuario,
        nome="Gastos",
        defaults={"tipo": Categoria.TIPO_DESPESA, "is_default": True},
    )
    cat_invest, _ = Categoria.objects.get_or_create(
        created_by=usuario,
        nome="Investimento",
        defaults={"tipo": Categoria.TIPO_DESPESA, "is_default": True},
    )
    return {"RECEITA": cat_receita, "GASTOS": cat_gastos, "INVESTIMENTO": cat_invest}


def classificar_tipo_e_categoria(desc_limpa: str, categorias_padrao):
    """
    Decide se é investimento (tipo I) ou despesa normal (tipo D),
    e define a categoria padrão correspondente.
    """
    s = (desc_limpa or "").strip().upper()
    if "INVEST" in s:
        return Conta.TIPO_INVESTIMENTO, categorias_padrao["INVESTIMENTO"]
    return Conta.TIPO_DESPESA, categorias_padrao["GASTOS"]


def upsert_conta_legado(
    *,
    usuario,
    tipo,
    descricao,
    valor,
    data_prevista,
    transacao_realizada,
    data_realizacao,
    categoria,
    forma_pagamento,
    is_legacy,
    origem_ano,
    origem_mes,
    origem_linha,
):
    """
    Dedupe por chave forte + mantém rastreio legado.
    Se existir, atualiza campos principais conforme sua resposta (7).
    """
    # chave forte
    conta = Conta.objects.filter(
        created_by=usuario,
        tipo=tipo,
        descricao=descricao,
        valor=valor,
        data_prevista=data_prevista,
    ).first()

    if not conta:
        # fallback pelo rastreio legado (caso o valor/descricao mude mas origem seja igual)
        conta = Conta.objects.filter(
            created_by=usuario,
            is_legacy=True,
            origem_ano=origem_ano,
            origem_mes=origem_mes,
            origem_linha=origem_linha,
        ).first()

    if not conta:
        return Conta.objects.create(
            created_by=usuario,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
            data_prevista=data_prevista,
            transacao_realizada=transacao_realizada,
            data_realizacao=data_realizacao,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            is_legacy=is_legacy,
            origem_ano=origem_ano,
            origem_mes=origem_mes,
            origem_linha=origem_linha,
        )

    # atualiza conforme sua regra (7)
    conta.tipo = tipo
    conta.descricao = descricao
    conta.valor = valor
    conta.data_prevista = data_prevista
    conta.transacao_realizada = transacao_realizada
    conta.data_realizacao = data_realizacao
    conta.categoria = categoria
    conta.forma_pagamento = forma_pagamento
    conta.is_legacy = is_legacy
    conta.origem_ano = origem_ano
    conta.origem_mes = origem_mes
    conta.origem_linha = origem_linha
    conta.save()
    return conta


@transaction.atomic
def importar_planilha_legado_padrao(arquivo, usuario, sobrescrever=False):
    """
    Regras (baseadas nas suas respostas):
    1) Importa linhas 'RECEITA' do topo como Conta (tipo Receita) REALIZADA
       com data_prevista = 5º dia útil do mês e data_realizacao = data_prevista
    2) Ignora linha 'GASTOS' do topo
    3) Cada linha em FIXOS EU/CASA/CARTAO vira Conta (despesa/investimento), data_prevista = vencimento
    4) Se vencimento no passado, já marca transacao_realizada=True e data_realizacao=vencimento
    5) Categoria sempre uma de: Receita, Gastos, Investimento
    6) FormaPagamento padronizada: PIX, Boleto, Cartão de Crédito, Cartão de Débito
    7) Se já existir, atualiza categoria/forma e também transacao_realizada/data_realizacao
    8) Dedupe por chave forte + rastreio legado
    16) sobrescrever=True apaga tudo do usuário (Conta)
    18) Receita do mês entra no 5º dia útil do mês
    """
    if sobrescrever:
        Conta.objects.filter(created_by=usuario).delete()

    cats = get_or_create_categorias_padrao(usuario)
    formas_padrao = get_or_create_formas_padrao(usuario)

    xls = pd.ExcelFile(arquivo)
    hoje = timezone.localdate()

    for aba in xls.sheet_names:
        if not str(aba).strip().isdigit():
            continue
        ano = int(str(aba).strip())

        df = pd.read_excel(arquivo, sheet_name=aba, header=None, dtype=object)
        df = (
            df.dropna(axis=1, how="all")
            .dropna(axis=0, how="all")
            .reset_index(drop=True)
        )

        secao = "RESUMO"
        meses_col_map = {}

        # para o ResumoMensal (planejado do excel)
        receita_por_mes = {m: Decimal("0") for m in range(1, 13)}
        gasto_por_mes = {m: Decimal("0") for m in range(1, 13)}

        receita_idx = 0

        for i in range(len(df)):
            row = df.iloc[i].tolist()
            primeira = row[0] if row else None
            linha = str(primeira).strip().upper() if primeira is not None else ""

            header = detectar_header_meses(row)
            if header:
                meses_col_map = header
                if linha in SECOES:
                    secao = linha
                continue

            if not meses_col_map:
                continue

            if linha in IGNORAR_LINHAS:
                continue
            if linha in SECOES:
                secao = linha
                continue
            if "SUB-TOTAL" in linha or linha == "TOTAL":
                continue

            # -------------- TOPO: RECEITAS --------------
            if secao == "RESUMO":
                if linha == "RECEITA":
                    receita_idx += 1
                    desc = f"Receita {receita_idx}"

                    forma_receita = inferir_forma_pagamento(
                        desc=desc,
                        secao=secao,
                        is_receita=True,
                        formas_padrao=formas_padrao,
                    )

                    for col_idx, mes_num in meses_col_map.items():
                        valor = parse_brl(row[col_idx] if col_idx < len(row) else None)
                        if valor <= 0:
                            continue

                        dt = quinto_dia_util(ano, mes_num)
                        origem = f"RECEITA_{receita_idx}"

                        upsert_conta_legado(
                            created_by=usuario,
                            tipo=Conta.TIPO_RECEITA,
                            descricao=desc,
                            valor=valor,
                            data_prevista=dt,
                            transacao_realizada=True,
                            data_realizacao=dt,
                            categoria=cats["RECEITA"],
                            forma_pagamento=forma_receita,
                            is_legacy=True,
                            origem_ano=ano,
                            origem_mes=mes_num,
                            origem_linha=origem,
                        )

                        receita_por_mes[mes_num] += valor

                # Ignora completamente 'GASTOS' do topo e qualquer outro no resumo
                continue

            # -------------- SEÇÕES: DESPESAS / INVESTIMENTOS --------------
            desc_original = str(primeira).strip()
            desc_limpa = limpar_descricao(desc_original)
            dia_venc = extrair_dia_vencimento(desc_original) or 1

            tipo_conta, categoria = classificar_tipo_e_categoria(desc_limpa, cats)

            forma_pagamento = inferir_forma_pagamento(
                desc=desc_limpa,
                secao=secao,
                is_receita=False,
                formas_padrao=formas_padrao,
            )

            for col_idx, mes_num in meses_col_map.items():
                valor = parse_brl(row[col_idx] if col_idx < len(row) else None)
                if valor <= 0:
                    continue

                dia_ok = ajustar_dia(ano, mes_num, dia_venc)
                venc = date(ano, mes_num, dia_ok)

                realizada = venc < hoje
                data_realizacao = venc if realizada else None

                origem = f"CONTA:{secao}:{desc_limpa}"

                upsert_conta_legado(
                    created_by=usuario,
                    tipo=tipo_conta,
                    descricao=desc_limpa,
                    valor=valor,
                    data_prevista=venc,
                    transacao_realizada=realizada,
                    data_realizacao=data_realizacao,
                    categoria=categoria,
                    forma_pagamento=forma_pagamento,
                    is_legacy=True,
                    origem_ano=ano,
                    origem_mes=mes_num,
                    origem_linha=origem,
                )

                gasto_por_mes[mes_num] += valor

    return True
