"""Testes da projeção de saldo e do calendário de pagamentos.

A propriedade central é a **ancoragem**: o saldo do primeiro dia projetado é o
dinheiro que existe hoje, não zero. Sem isso a tela mostra fluxo líquido disfarçado
de saldo e a pergunta "em que dia eu fico negativo?" erra por um valor constante.

Em seguida, o **filtro de cartão**: compra individual e fatura consolidada são o
mesmo dinheiro em dois níveis de registro. A âncora (`saldo_liquidez_ate`) aplica o
filtro, e o fluxo futuro precisa aplicar o mesmo, senão medem universos diferentes.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    CartaoCredito,
    Categoria,
    Conta,
    ConfigUsuario,
    LancamentoRecorrente,
    MetaFinanceira,
)
from core.services.projecao_service import calendario_mes, horizonte_saldos

User = get_user_model()


class ProjecaoBaseTestCase(TestCase):
    """Base com um usuário limpo e auxiliares de criação de lançamento."""

    def setUp(self):
        """Cria o usuário e fixa uma data de referência estável."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.hoje = date(2026, 3, 10)

    def lancar(self, tipo: str, valor: str, data_prevista: date, realizada: bool = False,
               data_realizacao=None, cartao=None, eh_fatura: bool = False):
        """Cria um lançamento com o mínimo de parâmetros.

        Returns:
            Conta: O lançamento criado.
        """
        return Conta.objects.create(
            usuario=self.user,
            tipo=tipo,
            descricao="Lançamento de teste",
            valor=Decimal(valor),
            data_prevista=data_prevista,
            transacao_realizada=realizada,
            data_realizacao=data_realizacao or (data_prevista if realizada else None),
            cartao=cartao,
            eh_fatura_cartao=eh_fatura,
        )

    def saldo_do_dia(self, projecao: dict, alvo: date, campo: str = "saldo") -> Decimal:
        """Extrai o saldo projetado de uma data específica.

        Args:
            campo: "saldo" ou "saldo_com_metas".

        Returns:
            Decimal: Saldo daquele dia.

        Raises:
            AssertionError: Se a data não estiver na janela projetada.
        """
        for mes in projecao["meses"]:
            for dia in mes["dias"]:
                if dia["data"] == alvo.isoformat():
                    return Decimal(dia[campo])
        raise AssertionError(f"{alvo} não está na janela projetada.")


class AncoragemDoSaldoTests(ProjecaoBaseTestCase):
    """Verifica que a projeção parte do dinheiro que já existe."""

    def test_projecao_parte_do_saldo_realizado(self):
        """A curva começa no caixa de hoje, não em zero."""
        self.lancar(Conta.TIPO_RECEITA, "5000.00", self.hoje - timedelta(days=30),
                    realizada=True)
        self.lancar(Conta.TIPO_DESPESA, "1200.00", self.hoje - timedelta(days=20),
                    realizada=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("3800.00"))
        self.assertEqual(self.saldo_do_dia(projecao, self.hoje), Decimal("3800.00"))

    def test_lancamento_previsto_para_hoje_entra_como_movimento(self):
        """Evita contar duas vezes: a âncora vai até ontem, hoje é movimento.

        Se a âncora incluísse hoje e o dia também somasse o previsto, um
        lançamento de hoje apareceria dobrado.
        """
        self.lancar(Conta.TIPO_RECEITA, "1000.00", self.hoje - timedelta(days=5),
                    realizada=True)
        self.lancar(Conta.TIPO_DESPESA, "300.00", self.hoje)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("1000.00"))
        self.assertEqual(self.saldo_do_dia(projecao, self.hoje), Decimal("700.00"))

    def test_pendencia_vencida_entra_na_abertura(self):
        """Conta atrasada é dinheiro que ainda vai sair, não dado descartável."""
        self.lancar(Conta.TIPO_RECEITA, "2000.00", self.hoje - timedelta(days=10),
                    realizada=True)
        # Venceu e segue em aberto.
        self.lancar(Conta.TIPO_DESPESA, "500.00", self.hoje - timedelta(days=3))

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["atrasados"]["despesas"]), Decimal("500.00"))
        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("1500.00"))

    def test_dias_anteriores_a_hoje_nao_aparecem_na_janela(self):
        """O primeiro mês começa em hoje: o passado já está na âncora."""
        projecao = horizonte_saldos(self.user, self.hoje, meses=1)
        primeiro_mes = projecao["meses"][0]

        self.assertEqual(primeiro_mes["dias"][0]["dia"], self.hoje.day)
        self.assertTrue(all(d["dia"] >= self.hoje.day for d in primeiro_mes["dias"]))


class PontoCegoDoLiquidadoTests(ProjecaoBaseTestCase):
    """Cobre a fronteira entre a âncora e o fluxo.

    A âncora leva `data_realizacao <= ontem` e os pendentes entram por
    `data_prevista`. Quem for liquidado com data de hoje em diante não pertence a
    nenhum dos dois grupos por esses critérios, e antes da correção sumia da
    projeção — dinheiro real que a curva simplesmente não enxergava. O importador
    de extrato produz esse registro sozinho: ele marca a linha como realizada com
    a data do extrato, mesmo quando ela ainda não chegou.
    """

    def test_liquidado_com_data_futura_entra_no_fluxo(self):
        """Receita marcada como recebida numa data futura não pode sumir."""
        self.lancar(Conta.TIPO_RECEITA, "1000.00", self.hoje - timedelta(days=5),
                    realizada=True)
        # Salário de daqui a uma semana, já marcado como recebido na importação.
        futuro = self.hoje + timedelta(days=7)
        self.lancar(Conta.TIPO_RECEITA, "4593.68", futuro, realizada=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        # A âncora corta em ontem, então o lançamento futuro fica fora dela.
        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("1000.00"))
        self.assertEqual(self.saldo_do_dia(projecao, self.hoje), Decimal("1000.00"))
        # E aparece no dia em que o dinheiro entra.
        self.assertEqual(self.saldo_do_dia(projecao, futuro), Decimal("5593.68"))

    def test_liquidado_hoje_conta_uma_vez_so(self):
        """A fronteira exata: liquidado hoje entra pelo fluxo, e só por ele."""
        self.lancar(Conta.TIPO_RECEITA, "2000.00", self.hoje - timedelta(days=2),
                    realizada=True)
        self.lancar(Conta.TIPO_DESPESA, "300.00", self.hoje, realizada=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("2000.00"))
        self.assertEqual(self.saldo_do_dia(projecao, self.hoje), Decimal("1700.00"))

    def test_liquidado_e_pendente_no_mesmo_dia_somam(self):
        """As duas populações convivem sem uma anular a outra."""
        alvo = self.hoje + timedelta(days=3)
        self.lancar(Conta.TIPO_RECEITA, "500.00", alvo, realizada=True)
        self.lancar(Conta.TIPO_DESPESA, "200.00", alvo)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(self.saldo_do_dia(projecao, alvo), Decimal("300.00"))

    def test_liquidado_pela_data_de_realizacao_e_nao_pela_prevista(self):
        """O que governa o liquidado é quando o dinheiro andou, não o vencimento."""
        prevista = self.hoje - timedelta(days=10)
        realizacao = self.hoje + timedelta(days=4)
        self.lancar(Conta.TIPO_DESPESA, "800.00", prevista, realizada=True,
                    data_realizacao=realizacao)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        # Já liquidada, então não é pendência atrasada.
        self.assertEqual(Decimal(projecao["atrasados"]["despesas"]), Decimal("0.00"))
        self.assertEqual(self.saldo_do_dia(projecao, self.hoje), Decimal("0.00"))
        self.assertEqual(self.saldo_do_dia(projecao, realizacao), Decimal("-800.00"))

    def test_liquidado_alem_da_janela_nao_entra(self):
        """Fora do horizonte é fora do horizonte, liquidado ou não."""
        self.lancar(Conta.TIPO_RECEITA, "1000.00", self.hoje - timedelta(days=1),
                    realizada=True)
        self.lancar(Conta.TIPO_RECEITA, "9999.00", date(2027, 6, 1), realizada=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)
        ultimo_dia = projecao["meses"][-1]["dias"][-1]

        self.assertEqual(Decimal(ultimo_dia["saldo"]), Decimal("1000.00"))

    def test_compra_de_cartao_liquidada_nao_dobra_com_a_fatura(self):
        """O filtro de cartão vale para as duas metades do fluxo.

        Sem ele na consulta dos liquidados, a correção reabriria justamente a
        dupla contagem que o filtro existe para impedir. Como o signal
        `monitorar_salvamento_conta` consolida a fatura assim que a compra é
        salva, o desembolso esperado é o da fatura — uma vez, não duas.
        """
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão", limite=Decimal("5000.00"),
            dia_fechamento=1, dia_vencimento=10,
        )
        alvo = self.hoje + timedelta(days=5)
        self.lancar(Conta.TIPO_DESPESA, "400.00", alvo, realizada=True, cartao=cartao)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        # -800.00 seria compra + fatura somadas; -400.00 é o desembolso real.
        self.assertEqual(self.saldo_do_dia(projecao, alvo), Decimal("-400.00"))


class FiltroDeCartaoTests(ProjecaoBaseTestCase):
    """Verifica que compra de cartão e fatura não são somadas juntas."""

    def setUp(self):
        """Cria um cartão de crédito para os lançamentos do teste."""
        super().setUp()
        self.cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão de teste",
            limite=Decimal("5000.00"), dia_fechamento=1, dia_vencimento=10,
        )

    def test_compra_individual_sai_do_caixa_uma_vez_so(self):
        """Registrar uma compra de cartão desconta o valor exatamente uma vez.

        Não é possível ter a compra isolada no banco: o signal
        `monitorar_salvamento_conta` consolida a fatura do período assim que a
        compra é salva. Então o que este teste garante não é que a compra seja
        ignorada, e sim que compra e fatura juntas produzam um único desembolso —
        o da fatura.
        """
        vencimento = self.hoje + timedelta(days=20)
        self.lancar(Conta.TIPO_DESPESA, "800.00", vencimento,
                    cartao=self.cartao, eh_fatura=False)

        # A fatura consolidada foi criada pelo signal, não pelo teste.
        self.assertTrue(
            Conta.objects.filter(
                usuario=self.user, eh_fatura_cartao=True, cartao=self.cartao
            ).exists()
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)
        self.assertEqual(self.saldo_do_dia(projecao, vencimento), Decimal("-800.00"))

    def test_fatura_consolidada_afeta_a_projecao(self):
        """A fatura é o que efetivamente sai do caixa."""
        vencimento = self.hoje + timedelta(days=20)
        self.lancar(Conta.TIPO_DESPESA, "800.00", vencimento,
                    cartao=self.cartao, eh_fatura=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)
        self.assertEqual(self.saldo_do_dia(projecao, vencimento), Decimal("-800.00"))

    def test_varias_compras_descontam_apenas_o_total_da_fatura(self):
        """O cenário real: N compras no mês, um único desembolso no vencimento.

        O valor da fatura é recalculado pelo `fatura_service` a partir das compras,
        então o esperado é a soma delas — e não a soma das compras *mais* a fatura.
        """
        vencimento = self.hoje + timedelta(days=20)
        self.lancar(Conta.TIPO_DESPESA, "300.00", vencimento,
                    cartao=self.cartao, eh_fatura=False)
        self.lancar(Conta.TIPO_DESPESA, "500.00", vencimento,
                    cartao=self.cartao, eh_fatura=False)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)
        self.assertEqual(self.saldo_do_dia(projecao, vencimento), Decimal("-800.00"))


class DespesaRecorrenteNaProjecaoTests(ProjecaoBaseTestCase):
    """Verifica o motivo pelo qual a recorrência foi generalizada."""

    def test_despesa_recorrente_e_materializada_por_toda_a_janela(self):
        """Sem isto, a projeção de 12 meses ficaria otimista.

        A receita fixa era materializada um ano à frente e a despesa fixa não
        existia fora dos meses lançados à mão, então o saldo subia de forma irreal.
        """
        categoria = Categoria.objects.filter(
            usuario=self.user, tipo=Categoria.TIPO_DESPESA
        ).first()
        LancamentoRecorrente.objects.create(
            usuario=self.user,
            tipo=LancamentoRecorrente.TIPO_DESPESA,
            descricao="Aluguel",
            categoria=categoria,
            valor=Decimal("2000.00"),
            frequencia=LancamentoRecorrente.FREQ_MENSAL,
            data_inicio=self.hoje,
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=12)

        # O aluguel precisa aparecer em todos os doze meses da janela.
        meses_com_despesa = [
            m["rotulo"] for m in projecao["meses"]
            if Decimal(m["total_despesas"]) > 0
        ]
        self.assertEqual(len(meses_com_despesa), 12, meses_com_despesa)

        # E o saldo final tem de refletir doze aluguéis.
        ultimo_mes = projecao["meses"][-1]
        self.assertEqual(
            Decimal(ultimo_mes["saldo_final"]), Decimal("-24000.00")
        )

    def test_regra_de_receita_continua_gerando_receita(self):
        """A generalização não pode inverter o comportamento existente."""
        LancamentoRecorrente.objects.create(
            usuario=self.user,
            tipo=LancamentoRecorrente.TIPO_RECEITA,
            descricao="Salário",
            valor=Decimal("4000.00"),
            frequencia=LancamentoRecorrente.FREQ_MENSAL,
            data_inicio=self.hoje,
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=3)
        self.assertEqual(
            Decimal(projecao["meses"][0]["total_receitas"]), Decimal("4000.00")
        )
        self.assertEqual(
            Decimal(projecao["meses"][0]["total_despesas"]), Decimal("0.00")
        )


class ValorInvestidoNoHorizonteTests(ProjecaoBaseTestCase):
    """Cobre o recorte de liquidez: quanto sobra fora da carteira.

    Caixa e carteira se sobrepõem quando a compra do ativo não foi lançada como
    despesa: o mesmo dinheiro aparece no saldo e no patrimônio. O padrão é a
    leitura conservadora — dinheiro aplicado não paga conta —, e somar a carteira
    de volta é que exige pedido explícito.
    """

    def _ativo(self, ticker: str, quantidade: str, preco_medio: str):
        """Cria uma posição na carteira do usuário de teste.

        Returns:
            Ativo: A posição persistida.
        """
        from investimento.models import Ativo

        return Ativo.objects.create(
            usuario=self.user, ticker=ticker,
            quantidade=Decimal(quantidade), preco_medio=Decimal(preco_medio),
        )

    def test_por_padrao_o_investido_fica_fora_do_saldo(self):
        """Sem pedir nada, a projeção mostra só o dinheiro líquido."""
        self.lancar(Conta.TIPO_RECEITA, "5000.00", self.hoje - timedelta(days=2),
                    realizada=True)
        self._ativo("XPTO11", "100", "20.00")

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["valor_investido"]), Decimal("2000.00"))
        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("3000.00"))
        self.assertFalse(projecao["investimentos_considerados"])

    def test_considerar_devolve_a_carteira_ao_saldo(self):
        """Ligado, o saldo volta a ser o patrimônio inteiro."""
        self.lancar(Conta.TIPO_RECEITA, "5000.00", self.hoje - timedelta(days=2),
                    realizada=True)
        self._ativo("XPTO11", "100", "20.00")

        projecao = horizonte_saldos(self.user, self.hoje, meses=1,
                                    considerar_investimentos=True)

        self.assertEqual(Decimal(projecao["saldo_inicial"]), Decimal("5000.00"))
        self.assertTrue(projecao["investimentos_considerados"])

    def test_valor_investido_vai_na_resposta_nos_dois_modos(self):
        """A interface precisa do número para rotular o botão antes do clique."""
        self._ativo("XPTO11", "10", "33.33")

        for considerar in (False, True):
            projecao = horizonte_saldos(self.user, self.hoje, meses=1,
                                        considerar_investimentos=considerar)
            self.assertEqual(
                Decimal(projecao["valor_investido"]), Decimal("333.30")
            )

    def test_soma_todas_as_posicoes(self):
        """Uma carteira é a soma das posições, não a maior delas."""
        self._ativo("AAAA11", "10", "15.00")
        self._ativo("BBBB11", "5", "40.00")

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["valor_investido"]), Decimal("350.00"))

    def test_carteira_fora_do_saldo_nao_entra_no_valor_investido(self):
        """O critério é liquidez: ações não são dinheiro em caixa; a reserva é."""
        from investimento.models import Carteira, PosicaoCarteira

        reserva = Carteira.objects.get(usuario=self.user)
        reserva.nome = "Reserva"
        reserva.save(update_fields=["nome"])
        acoes = Carteira.objects.create(
            usuario=self.user, nome="Ações", considerar_no_saldo=False
        )

        selic = self._ativo("SELIC11", "10", "15.00")
        petr = self._ativo("PETR4", "5", "40.00")
        PosicaoCarteira.objects.create(
            usuario=self.user, carteira=reserva, ativo=selic,
            quantidade=Decimal("10"), preco_medio=Decimal("15.00"),
        )
        PosicaoCarteira.objects.create(
            usuario=self.user, carteira=acoes, ativo=petr,
            quantidade=Decimal("5"), preco_medio=Decimal("40.00"),
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        # 150 da reserva + 200 das ações = 350; as ações ficam de fora.
        self.assertEqual(Decimal(projecao["valor_investido"]), Decimal("150.00"))
        self.assertEqual(projecao["carteiras_consideradas"], ["Reserva"])

    def test_todas_as_carteiras_contam_por_padrao(self):
        """Quem nunca mexeu na configuração precisa ver o valor de sempre."""
        self._ativo("AAAA11", "10", "15.00")

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["valor_investido"]), Decimal("150.00"))

    def test_carteira_de_outro_usuario_nao_entra(self):
        """Vazamento aqui apareceria como saldo a menos, sem explicação na tela."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        from investimento.models import Ativo
        Ativo.objects.create(usuario=outro, ticker="ZZZZ11",
                             quantidade=Decimal("1000"), preco_medio=Decimal("50.00"))

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)

        self.assertEqual(Decimal(projecao["valor_investido"]), Decimal("0.00"))

    def test_sem_carteira_os_dois_modos_coincidem(self):
        """Quem não investe não pode ver diferença entre ligado e desligado."""
        self.lancar(Conta.TIPO_RECEITA, "800.00", self.hoje - timedelta(days=1),
                    realizada=True)

        padrao = horizonte_saldos(self.user, self.hoje, meses=1)
        considerando = horizonte_saldos(self.user, self.hoje, meses=1,
                                        considerar_investimentos=True)

        self.assertEqual(Decimal(padrao["valor_investido"]), Decimal("0.00"))
        self.assertEqual(
            Decimal(padrao["saldo_inicial"]), Decimal(considerando["saldo_inicial"])
        )

    def test_alternar_desloca_a_curva_sem_deformar(self):
        """É deslocamento constante: todo dia sobe o mesmo, e o fluxo não muda."""
        self.lancar(Conta.TIPO_RECEITA, "5000.00", self.hoje - timedelta(days=2),
                    realizada=True)
        self.lancar(Conta.TIPO_DESPESA, "700.00", self.hoje + timedelta(days=4))
        self._ativo("XPTO11", "100", "20.00")

        padrao = horizonte_saldos(self.user, self.hoje, meses=1)
        considerando = horizonte_saldos(self.user, self.hoje, meses=1,
                                        considerar_investimentos=True)

        diferencas = {
            Decimal(a["saldo"]) - Decimal(b["saldo"])
            for a, b in zip(considerando["meses"][0]["dias"], padrao["meses"][0]["dias"])
        }
        self.assertEqual(diferencas, {Decimal("2000.00")})

    def test_o_padrao_pode_revelar_um_dia_negativo(self):
        """O ponto do recurso: o estouro que o dinheiro aplicado escondia.

        Com a carteira somada, a despesa cabe no saldo. Sem ela, não cabe — e o
        dia do estouro é o da despesa, não hoje: até lá o caixa líquido é positivo.
        """
        vencimento = self.hoje + timedelta(days=5)
        self.lancar(Conta.TIPO_RECEITA, "2500.00", self.hoje - timedelta(days=2),
                    realizada=True)
        self.lancar(Conta.TIPO_DESPESA, "2200.00", vencimento)
        self._ativo("XPTO11", "100", "20.00")

        padrao = horizonte_saldos(self.user, self.hoje, meses=1)
        considerando = horizonte_saldos(self.user, self.hoje, meses=1,
                                        considerar_investimentos=True)

        self.assertIsNone(considerando["primeiro_dia_negativo"])
        self.assertEqual(padrao["primeiro_dia_negativo"], vencimento.isoformat())


class CenarioDeMetasTests(ProjecaoBaseTestCase):
    """Verifica que o aporte de metas é cenário, não compromisso."""

    def test_meta_nao_contamina_o_saldo_principal(self):
        """Aporte para meta é intenção de poupar, não despesa assumida."""
        MetaFinanceira.objects.create(
            usuario=self.user, nome="Reserva de emergência",
            valor_alvo=Decimal("6000.00"), valor_acumulado=Decimal("0.00"),
            prazo=self.hoje + relativedelta_meses(6),
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=6)

        self.assertEqual(self.saldo_do_dia(projecao, self.hoje), Decimal("0.00"))
        self.assertLess(
            self.saldo_do_dia(projecao, self.hoje, campo="saldo_com_metas"),
            Decimal("0.00"),
        )

    def test_meta_sem_prazo_e_ignorada(self):
        """Sem prazo não há cronograma dedutível; inventar um seria arbitrário."""
        MetaFinanceira.objects.create(
            usuario=self.user, nome="Casa própria",
            valor_alvo=Decimal("500000.00"), valor_acumulado=Decimal("0.00"),
            prazo=None,
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=6)
        self.assertEqual(
            self.saldo_do_dia(projecao, self.hoje, campo="saldo_com_metas"),
            Decimal("0.00"),
        )

    def test_meta_ja_atingida_nao_gera_aporte(self):
        """Valor faltante zero ou negativo não deve virar débito."""
        MetaFinanceira.objects.create(
            usuario=self.user, nome="Viagem",
            valor_alvo=Decimal("3000.00"), valor_acumulado=Decimal("3500.00"),
            prazo=self.hoje + relativedelta_meses(3),
        )

        projecao = horizonte_saldos(self.user, self.hoje, meses=3)
        self.assertEqual(
            self.saldo_do_dia(projecao, self.hoje, campo="saldo_com_metas"),
            Decimal("0.00"),
        )


class AlertaDeSaldoNegativoTests(ProjecaoBaseTestCase):
    """Verifica a detecção do primeiro dia negativo e a classificação dos dias."""

    def test_identifica_o_primeiro_dia_negativo(self):
        """É a resposta principal que a tela precisa dar."""
        self.lancar(Conta.TIPO_RECEITA, "1000.00", self.hoje - timedelta(days=1),
                    realizada=True)
        dia_do_estouro = self.hoje + timedelta(days=15)
        self.lancar(Conta.TIPO_DESPESA, "1500.00", dia_do_estouro)

        projecao = horizonte_saldos(self.user, self.hoje, meses=2)
        self.assertEqual(
            projecao["primeiro_dia_negativo"], dia_do_estouro.isoformat()
        )

    def test_sem_estouro_o_campo_fica_nulo(self):
        """Ausência de risco precisa ser distinguível de risco no primeiro dia."""
        self.lancar(Conta.TIPO_RECEITA, "1000.00", self.hoje - timedelta(days=1),
                    realizada=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=2)
        self.assertIsNone(projecao["primeiro_dia_negativo"])

    def test_limite_de_atencao_classifica_o_dia(self):
        """A faixa intermediária é o que permite agir antes de estourar."""
        self.lancar(Conta.TIPO_RECEITA, "500.00", self.hoje - timedelta(days=1),
                    realizada=True)

        projecao = horizonte_saldos(
            self.user, self.hoje, meses=1, limite_atencao=Decimal("1000.00")
        )
        primeiro_dia = projecao["meses"][0]["dias"][0]
        self.assertEqual(primeiro_dia["situacao"], "atencao")

    def test_sem_limite_nao_ha_faixa_intermediaria(self):
        """Sem limite configurado, só existe positivo ou negativo."""
        self.lancar(Conta.TIPO_RECEITA, "500.00", self.hoje - timedelta(days=1),
                    realizada=True)

        projecao = horizonte_saldos(self.user, self.hoje, meses=1)
        self.assertEqual(projecao["meses"][0]["dias"][0]["situacao"], "confortavel")


class CalendarioMesTests(ProjecaoBaseTestCase):
    """Verifica a grade mensal de pagamentos e recebimentos."""

    def test_lancamentos_ficam_no_dia_previsto(self):
        """O calendário organiza por `data_prevista`, não por realização."""
        self.lancar(Conta.TIPO_DESPESA, "250.00", date(2026, 3, 5))
        self.lancar(Conta.TIPO_RECEITA, "4000.00", date(2026, 3, 5))
        self.lancar(Conta.TIPO_DESPESA, "90.00", date(2026, 3, 20))

        grade = calendario_mes(self.user, 2026, 3)
        por_dia = {d["dia"]: d for d in grade["dias"]}

        self.assertEqual(len(por_dia[5]["lancamentos"]), 2)
        self.assertEqual(Decimal(por_dia[5]["total_receitas"]), Decimal("4000.00"))
        self.assertEqual(Decimal(por_dia[5]["total_despesas"]), Decimal("250.00"))
        self.assertEqual(len(por_dia[20]["lancamentos"]), 1)

    def test_grade_cobre_todos_os_dias_do_mes(self):
        """Dias vazios precisam existir para o calendário não ter buracos."""
        grade = calendario_mes(self.user, 2026, 2)
        self.assertEqual(grade["dias_no_mes"], 28)
        self.assertEqual(len(grade["dias"]), 28)

    def test_informa_o_dia_da_semana_do_primeiro_dia(self):
        """O cliente monta a grade sem recalcular o calendário."""
        grade = calendario_mes(self.user, 2026, 3)
        # 1 de março de 2026 é um domingo; segunda = 0, domingo = 6.
        self.assertEqual(grade["dia_semana_do_primeiro"], 6)

    def test_compra_de_cartao_aparece_mas_nao_soma_no_total(self):
        """Quem abre o calendário quer ver a compra; o total é o desembolso real."""
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão", limite=Decimal("5000.00"),
            dia_fechamento=1, dia_vencimento=10,
        )
        dia = date(2026, 3, 10)
        self.lancar(Conta.TIPO_DESPESA, "700.00", dia, cartao=cartao, eh_fatura=True)
        self.lancar(Conta.TIPO_DESPESA, "700.00", dia, cartao=cartao, eh_fatura=False)

        grade = calendario_mes(self.user, 2026, 3)
        do_dia = next(d for d in grade["dias"] if d["dia"] == 10)

        self.assertEqual(len(do_dia["lancamentos"]), 2)
        self.assertEqual(Decimal(do_dia["total_despesas"]), Decimal("700.00"))

    def test_conta_pendente_e_contabilizada(self):
        """O contador de pendências é o que sinaliza o dia que exige ação."""
        self.lancar(Conta.TIPO_DESPESA, "100.00", date(2026, 3, 8))
        self.lancar(Conta.TIPO_DESPESA, "100.00", date(2026, 3, 8), realizada=True)

        grade = calendario_mes(self.user, 2026, 3)
        do_dia = next(d for d in grade["dias"] if d["dia"] == 8)
        self.assertEqual(do_dia["pendentes"], 1)


def relativedelta_meses(n: int):
    """Devolve um deslocamento de `n` meses.

    Auxiliar local para manter os testes legíveis sem repetir o import.

    Returns:
        relativedelta: Deslocamento correspondente.
    """
    from dateutil.relativedelta import relativedelta

    return relativedelta(months=n)
