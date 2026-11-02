"""Confere o calendário de pregões contra a lista oficial da B3 para 2026.

Fonte: "Calendário de negociação da B3: confira o funcionamento da bolsa em 2026"
(b3.com.br, 09/01/2026). Se a B3 mudar a regra, este teste é o que avisa.
"""

import datetime

from django.test import SimpleTestCase

from investimento.services.calendario_b3 import (
    ABERTURA_PADRAO,
    ABERTURA_QUARTA_DE_CINZAS,
    abertura_do_dia,
    eh_dia_de_pregao,
    feriado_b3,
    feriados_b3,
    pascoa,
)

SEM_PREGAO_2026 = {
    datetime.date(2026, 1, 1),
    datetime.date(2026, 2, 16),
    datetime.date(2026, 2, 17),
    datetime.date(2026, 4, 3),
    datetime.date(2026, 4, 21),
    datetime.date(2026, 5, 1),
    datetime.date(2026, 6, 4),
    datetime.date(2026, 9, 7),
    datetime.date(2026, 10, 12),
    datetime.date(2026, 11, 2),
    datetime.date(2026, 11, 20),
    datetime.date(2026, 12, 24),
    datetime.date(2026, 12, 25),
    datetime.date(2026, 12, 31),
}


class CalendarioB3Tests(SimpleTestCase):
    def test_dias_uteis_sem_pregao_em_2026_batem_com_a_lista_oficial(self):
        # 15/11/2026 cai num domingo, por isso não aparece na lista oficial
        dias_uteis = {data for data in feriados_b3(2026) if data.weekday() < 5}
        self.assertEqual(dias_uteis, SEM_PREGAO_2026)

    def test_pascoa_em_anos_conhecidos(self):
        self.assertEqual(pascoa(2026), datetime.date(2026, 4, 5))
        self.assertEqual(pascoa(2027), datetime.date(2027, 3, 28))
        self.assertEqual(pascoa(2025), datetime.date(2025, 4, 20))

    def test_finados_nao_tem_pregao(self):
        self.assertEqual(feriado_b3(datetime.date(2026, 11, 2)), "Finados")
        self.assertFalse(eh_dia_de_pregao(datetime.date(2026, 11, 2)))

    def test_feriados_municipais_de_sao_paulo_tem_pregao(self):
        self.assertTrue(eh_dia_de_pregao(datetime.date(2026, 7, 9)))
        self.assertIsNone(feriado_b3(datetime.date(2027, 1, 25)))

    def test_quarta_de_cinzas_abre_mais_tarde(self):
        self.assertEqual(abertura_do_dia(datetime.date(2026, 2, 18)), ABERTURA_QUARTA_DE_CINZAS)
        self.assertEqual(abertura_do_dia(datetime.date(2026, 2, 19)), ABERTURA_PADRAO)
