import calendar
from datetime import date
from decimal import Decimal
from django.db import transaction
from core.models import Conta


def add_months(d: date, months: int) -> date:
    """Adiciona n meses a uma data, lidando com o fim do mês corretamente."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def cents_to_decimal(cents: int) -> Decimal:
    """Converte centavos (int) para Decimal monetário."""
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def criar_contas_multiplicadas(
    n: int,
    usuario,
    tipo,
    descricao,
    valor_total,
    data_prevista,
    pago,
    categoria,
    forma_pagamento,
    categoria_cartao,
    data_limite=None,
):
    with transaction.atomic():
        # Se houver data limite, calculamos o N dinamicamente
        if data_limite:
            # Garantimos que n seja pelo menos 1 (a própria conta atual)
            # Mas vamos iterar mês a mês até passar o limite
            n = 0
            while True:
                next_date = add_months(data_prevista, n)
                if next_date > data_limite:
                    break
                n += 1
            
            if n == 0:
                n = 1 # Pelo menos a primeira conta se o limite for hoje

        contas = []
        for i in range(1, n + 1):
            venc = add_months(data_prevista, i - 1)
            contas.append(
                Conta(
                    usuario=usuario,
                    tipo=tipo,
                    descricao=descricao,
                    valor=valor_total,
                    data_prevista=venc,
                    transacao_realizada=pago,
                    data_realizacao=venc if pago else None,
                    categoria=categoria,
                    forma_pagamento=forma_pagamento,
                    categoria_cartao=categoria_cartao,
                    eh_parcelada=False,
                    parcela_numero=None,
                    parcela_total=None,
                    grupo_parcelamento=None,
                )
            )
        Conta.objects.bulk_create(contas)


def criar_contas_parceladas(
    n: int,
    usuario,
    tipo,
    descricao,
    valor_total,
    data_prevista,
    pago,
    categoria,
    forma_pagamento,
    categoria_cartao,
):
    total_cents = int((valor_total * 100).to_integral_value())
    base = total_cents // n
    resto = total_cents % n

    with transaction.atomic():
        cents_1 = base + (1 if 1 <= resto else 0)

        primeira = Conta.objects.create(
            usuario=usuario,
            tipo=tipo,
            descricao=descricao,
            valor=cents_to_decimal(cents_1),
            data_prevista=data_prevista,
            transacao_realizada=pago,
            data_realizacao=data_prevista if pago else None,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            categoria_cartao=categoria_cartao,
            eh_parcelada=True,
            parcela_numero=1,
            parcela_total=n,
            grupo_parcelamento=None,
        )

        gid = primeira.id
        primeira.grupo_parcelamento = gid
        primeira.save(update_fields=["grupo_parcelamento", "atualizada_em"])

        contas = []
        for i in range(2, n + 1):
            cents = base + (1 if i <= resto else 0)
            venc = add_months(data_prevista, i - 1)

            contas.append(
                Conta(
                    usuario=usuario,
                    tipo=tipo,
                    descricao=descricao,
                    valor=cents_to_decimal(cents),
                    data_prevista=venc,
                    transacao_realizada=pago,
                    data_realizacao=venc if pago else None,
                    categoria=categoria,
                    forma_pagamento=forma_pagamento,
                    categoria_cartao=categoria_cartao,
                    eh_parcelada=True,
                    parcela_numero=i,
                    parcela_total=n,
                    grupo_parcelamento=gid,
                )
            )

        if contas:
            Conta.objects.bulk_create(contas)
