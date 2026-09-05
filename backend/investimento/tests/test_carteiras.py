"""Testes das carteiras de investimento (custódia por corretora ou banco).

Cobrem as três promessas do desenho: o ativo continua único mesmo aparecendo em
duas custódias, a posição por carteira é derivada e coerente com o consolidado, e
transferir entre carteiras não mexe no preço médio fiscal.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from investimento.models import (
    Ativo,
    Carteira,
    CarteiraHistorico,
    Cotacao,
    PosicaoCarteira,
    Transacao,
)
from investimento.services.carteira_historico_service import CarteiraHistoricoService


class CarteiraBaseTestCase(APITestCase):
    """Base com usuário autenticado, duas carteiras e um ativo."""

    def setUp(self):
        """Cria o investidor, autentica por JWT e monta duas custódias."""
        self.user = User.objects.create_user(
            username="investidor-carteiras", password="senha-bem-comprida-123"
        )
        token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # O signal já cria a Carteira Padrão ao registrar o usuário.
        self.xp = Carteira.objects.get(usuario=self.user)
        self.xp.nome = "XP"
        self.xp.save(update_fields=["nome"])

        self.inter = Carteira.objects.create(
            usuario=self.user, nome="Inter", instituicao="Banco Inter"
        )
        self.ativo = Ativo.objects.create(
            usuario=self.user, ticker="PETR4", nome="Petrobras"
        )

    def comprar(self, carteira, quantidade, preco, data=None):
        """Registra uma compra na carteira indicada.

        Returns:
            Transacao: A ordem criada.
        """
        quantidade = Decimal(str(quantidade))
        preco = Decimal(str(preco))
        return Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            carteira=carteira,
            tipo=Transacao.TIPO_COMPRA,
            data=data or timezone.localdate(),
            quantidade=quantidade,
            preco_unitario=preco,
            valor_total=quantidade * preco,
        )


class MesmoTickerEmDuasCarteirasTests(CarteiraBaseTestCase):
    """A razão de a carteira ficar na transação, e não no ativo."""

    def test_o_ativo_continua_unico(self):
        """Duplicar o ativo por corretora traria duas séries de cotação do mesmo papel."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        self.assertEqual(Ativo.objects.filter(usuario=self.user, ticker="PETR4").count(), 1)

    def test_a_cotacao_nao_e_duplicada(self):
        """Uma cotação por ticker e dia — o mercado não muda por corretora."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")
        Cotacao.objects.create(
            ativo=self.ativo, data=timezone.localdate(), valor=Decimal("35.00")
        )

        self.assertEqual(Cotacao.objects.filter(ativo__usuario=self.user).count(), 1)

    def test_cada_carteira_ganha_sua_posicao(self):
        """A quantidade por custódia é o que o filtro da tela vai ler."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        posicoes = {p.carteira_id: p for p in PosicaoCarteira.objects.filter(ativo=self.ativo)}
        self.assertEqual(posicoes[self.xp.id].quantidade, Decimal("100"))
        self.assertEqual(posicoes[self.xp.id].preco_medio, Decimal("30.0000"))
        self.assertEqual(posicoes[self.inter.id].quantidade, Decimal("50"))
        self.assertEqual(posicoes[self.inter.id].preco_medio, Decimal("40.0000"))

    def test_o_preco_medio_consolidado_e_o_fiscal(self):
        """O PM do CPF pondera as duas custódias: (100×30 + 50×40) / 150."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        self.ativo.refresh_from_db()
        self.assertEqual(self.ativo.quantidade, Decimal("150"))
        self.assertEqual(
            self.ativo.preco_medio.quantize(Decimal("0.0001")),
            Decimal("33.3333"),
        )

    def test_a_soma_das_posicoes_bate_com_o_consolidado(self):
        """A invariante que sustenta o dashboard e o Horizonte de Saldos.

        A comparação é em centavos porque `preco_medio` tem 4 casas: o consolidado
        de 150 cotas a 33,3333 fecha em 4.999,995, e a soma das posições — que não
        passa por essa divisão — em 5.000. A diferença é do arredondamento do campo,
        não do cálculo, e some no `_centavos` de quem consome.
        """
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        self.ativo.refresh_from_db()
        soma = sum(
            p.quantidade * p.preco_medio
            for p in PosicaoCarteira.objects.filter(ativo=self.ativo)
        )
        consolidado = self.ativo.quantidade * self.ativo.preco_medio
        self.assertEqual(
            soma.quantize(Decimal("0.01")), consolidado.quantize(Decimal("0.01"))
        )


class RecalculoDePosicaoTests(CarteiraBaseTestCase):
    """A posição é cache: precisa acompanhar edições, exclusões e zeragem."""

    def test_mudar_a_carteira_da_ordem_nao_deixa_posicao_obsoleta(self):
        """O gatilho só enxerga a carteira nova; a antiga tem de ser recalculada também."""
        ordem = self.comprar(self.xp, 100, "30.00")

        ordem.carteira = self.inter
        ordem.save()

        na_xp = PosicaoCarteira.objects.get(carteira=self.xp, ativo=self.ativo)
        no_inter = PosicaoCarteira.objects.get(carteira=self.inter, ativo=self.ativo)
        self.assertEqual(na_xp.quantidade, Decimal("0"))
        self.assertEqual(no_inter.quantidade, Decimal("100"))

    def test_zerar_a_posicao_preserva_a_meta_configurada(self):
        """A meta é intenção do usuário; o recálculo não pode levá-la junto."""
        ordem = self.comprar(self.xp, 100, "30.00")
        PosicaoCarteira.objects.filter(carteira=self.xp, ativo=self.ativo).update(
            meta_porcentagem=Decimal("25.00")
        )

        ordem.delete()

        posicao = PosicaoCarteira.objects.get(carteira=self.xp, ativo=self.ativo)
        self.assertEqual(posicao.quantidade, Decimal("0"))
        self.assertEqual(posicao.meta_porcentagem, Decimal("25.00"))

    def test_venda_abate_apenas_a_carteira_onde_ocorreu(self):
        """Vender na XP não pode encolher a posição do Inter."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        Transacao.objects.create(
            usuario=self.user, ativo=self.ativo, carteira=self.xp,
            tipo=Transacao.TIPO_VENDA, data=timezone.localdate(),
            quantidade=Decimal("40"), preco_unitario=Decimal("50.00"),
            valor_total=Decimal("2000.00"),
        )

        na_xp = PosicaoCarteira.objects.get(carteira=self.xp, ativo=self.ativo)
        no_inter = PosicaoCarteira.objects.get(carteira=self.inter, ativo=self.ativo)
        self.assertEqual(na_xp.quantidade, Decimal("60"))
        self.assertEqual(no_inter.quantidade, Decimal("50"))


class TransferenciaEntreCarteirasTests(CarteiraBaseTestCase):
    """Portabilidade não é venda: mudar de corretora não realiza lucro."""

    def transferir(self, origem, destino, quantidade):
        """Chama o endpoint de transferência.

        Returns:
            Response: A resposta da API.
        """
        return self.client.post(
            "/api/investimentos/transacoes/transferir/",
            {
                "ativo": self.ativo.id,
                "origem": origem.id,
                "destino": destino.id,
                "quantidade": str(quantidade),
            },
            format="json",
        )

    def test_transferir_nao_altera_o_preco_medio_fiscal(self):
        """O ponto do tipo próprio: venda + compra falsas moveriam o PM."""
        self.comprar(self.xp, 100, "30.00")
        self.ativo.refresh_from_db()
        pm_antes = self.ativo.preco_medio

        resposta = self.transferir(self.xp, self.inter, 40)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

        self.ativo.refresh_from_db()
        self.assertEqual(self.ativo.preco_medio, pm_antes)
        self.assertEqual(self.ativo.quantidade, Decimal("100"))

    def test_transferir_move_a_quantidade_entre_as_custodias(self):
        """O efeito visível: a mesma posição, em outro lugar."""
        self.comprar(self.xp, 100, "30.00")

        self.transferir(self.xp, self.inter, 40)

        na_xp = PosicaoCarteira.objects.get(carteira=self.xp, ativo=self.ativo)
        no_inter = PosicaoCarteira.objects.get(carteira=self.inter, ativo=self.ativo)
        self.assertEqual(na_xp.quantidade, Decimal("60"))
        self.assertEqual(no_inter.quantidade, Decimal("40"))
        self.assertEqual(no_inter.preco_medio, Decimal("30.0000"))

    def test_transferir_sem_saldo_e_recusado(self):
        """Sem a checagem, a origem ficaria com quantidade negativa."""
        self.comprar(self.xp, 10, "30.00")

        resposta = self.transferir(self.xp, self.inter, 50)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantidade", resposta.data)

    def test_transferir_para_a_mesma_carteira_e_recusado(self):
        """Uma transferência sem destino diferente é ruído no extrato."""
        self.comprar(self.xp, 100, "30.00")

        resposta = self.transferir(self.xp, self.xp, 10)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apagar_uma_perna_apaga_a_transferencia_inteira(self):
        """Meia transferência criaria ou destruiria cotas do nada."""
        self.comprar(self.xp, 100, "30.00")
        self.transferir(self.xp, self.inter, 40)

        perna = Transacao.objects.filter(tipo=Transacao.TIPO_TRANSF_SAIDA).first()
        self.client.delete(f"/api/investimentos/transacoes/{perna.id}/")

        self.assertEqual(
            Transacao.objects.filter(
                tipo__in=Transacao.TIPOS_TRANSFERENCIA
            ).count(),
            0,
        )
        na_xp = PosicaoCarteira.objects.get(carteira=self.xp, ativo=self.ativo)
        self.assertEqual(na_xp.quantidade, Decimal("100"))

    def test_perna_solta_nao_pode_ser_criada_pela_api_de_ordens(self):
        """O caminho é a ação `transferir/`, que grava as duas juntas."""
        resposta = self.client.post(
            "/api/investimentos/transacoes/",
            {
                "ativo": self.ativo.id,
                "carteira": self.xp.id,
                "tipo": Transacao.TIPO_TRANSF_ENTRADA,
                "data": timezone.localdate().isoformat(),
                "quantidade": "10",
                "preco_unitario": "30.00",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)


class HistoricoPorCarteiraTests(CarteiraBaseTestCase):
    """O snapshot diário ganhou a dimensão de custódia."""

    def test_gera_uma_serie_por_carteira(self):
        """Sem isso, filtrar por 'XP' mostraria o consolidado com cara de certo."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        CarteiraHistoricoService(self.user).atualizar()

        carteiras_com_historico = set(
            CarteiraHistorico.objects.filter(usuario=self.user).values_list(
                "carteira_id", flat=True
            )
        )
        self.assertEqual(carteiras_com_historico, {self.xp.id, self.inter.id})

    def test_serie_filtrada_traz_apenas_a_carteira_pedida(self):
        """O patrimônio da XP não inclui o que está custodiado no Inter."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")
        CarteiraHistoricoService(self.user).atualizar()

        serie_xp = CarteiraHistoricoService(self.user, self.xp.id).series_mensal(meses=12)
        serie_total = CarteiraHistoricoService(self.user).series_mensal(meses=12)

        self.assertEqual(serie_xp[-1]["patrimonio"], 3000.0)
        self.assertEqual(serie_total[-1]["patrimonio"], 5000.0)

    def test_transferencia_nao_infla_o_consolidado(self):
        """As pernas se anulam na soma; o patrimônio total não pode mudar."""
        self.comprar(self.xp, 100, "30.00")
        CarteiraHistoricoService(self.user).atualizar()
        antes = CarteiraHistoricoService(self.user).series_mensal(meses=12)[-1]

        self.client.post(
            "/api/investimentos/transacoes/transferir/",
            {
                "ativo": self.ativo.id, "origem": self.xp.id,
                "destino": self.inter.id, "quantidade": "40",
            },
            format="json",
        )
        CarteiraHistoricoService(self.user).atualizar()
        depois = CarteiraHistoricoService(self.user).series_mensal(meses=12)[-1]

        self.assertEqual(antes["patrimonio"], depois["patrimonio"])
        self.assertEqual(antes["investido"], depois["investido"])


class IsolamentoEntreUsuariosTests(CarteiraBaseTestCase):
    """Um id de carteira no corpo ou na querystring não pode furar o multi-tenant."""

    def setUp(self):
        """Acrescenta um segundo investidor, com carteira e ativo próprios."""
        super().setUp()
        self.outro = User.objects.create_user(
            username="outro-investidor", password="senha-bem-comprida-123"
        )
        self.carteira_alheia = Carteira.objects.get(usuario=self.outro)
        ativo_alheio = Ativo.objects.create(
            usuario=self.outro, ticker="VALE3", nome="Vale"
        )
        Transacao.objects.create(
            usuario=self.outro, ativo=ativo_alheio, carteira=self.carteira_alheia,
            tipo=Transacao.TIPO_COMPRA, data=timezone.localdate(),
            quantidade=Decimal("10"), preco_unitario=Decimal("60.00"),
            valor_total=Decimal("600.00"),
        )

    def test_listar_carteiras_nao_vaza_as_de_outro_usuario(self):
        """A lista é o que alimenta o seletor de filtro da tela."""
        resposta = self.client.get("/api/investimentos/carteiras/")

        nomes = {linha["nome"] for linha in resposta.data}
        self.assertEqual(nomes, {"XP", "Inter"})

    def test_filtrar_por_carteira_alheia_devolve_vazio(self):
        """Devolver vazio, e nunca os dados do outro: o filtro entra após o isolamento."""
        resposta = self.client.get(
            f"/api/investimentos/ativos/?carteira={self.carteira_alheia.id}"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data), 0)

    def test_lancar_ordem_em_carteira_alheia_e_recusado(self):
        """O `get_queryset` isola a leitura; a escrita precisa da própria checagem."""
        resposta = self.client.post(
            "/api/investimentos/transacoes/",
            {
                "ativo": self.ativo.id,
                "carteira": self.carteira_alheia.id,
                "tipo": Transacao.TIPO_COMPRA,
                "data": timezone.localdate().isoformat(),
                "quantidade": "1",
                "preco_unitario": "10.00",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("carteira", resposta.data)


class CicloDeVidaDaCarteiraTests(CarteiraBaseTestCase):
    """Arquivar em vez de excluir, para não levar o histórico junto."""

    def test_excluir_carteira_com_ordens_e_recusado(self):
        """A FK é PROTECT justamente para o histórico não sumir em cascata."""
        self.comprar(self.xp, 100, "30.00")

        resposta = self.client.delete(f"/api/investimentos/carteiras/{self.xp.id}/")

        self.assertEqual(resposta.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Carteira.objects.filter(pk=self.xp.id).exists())

    def test_carteira_vazia_pode_ser_excluida(self):
        """Sem histórico não há o que preservar — apagar é o que o usuário espera."""
        vazia = Carteira.objects.create(usuario=self.user, nome="Corretora fechada")

        resposta = self.client.delete(f"/api/investimentos/carteiras/{vazia.id}/")

        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

    def test_arquivar_preserva_as_ordens(self):
        """O caminho previsto: sai dos filtros, mas o histórico continua lá."""
        self.comprar(self.xp, 100, "30.00")

        resposta = self.client.patch(
            f"/api/investimentos/carteiras/{self.xp.id}/", {"ativa": False}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(Transacao.objects.filter(carteira=self.xp).count(), 1)

    def test_usuario_novo_ja_nasce_com_uma_carteira(self):
        """Toda ordem exige custódia; sem isso o primeiro cadastro falharia."""
        novo = User.objects.create_user(
            username="recem-chegado", password="senha-bem-comprida-123"
        )

        self.assertEqual(Carteira.objects.filter(usuario=novo).count(), 1)


class FiltroDeCarteiraNaAPITests(CarteiraBaseTestCase):
    """Sob filtro, os números do ativo passam a ser os daquela custódia."""

    def test_listagem_filtrada_reporta_a_quantidade_da_carteira(self):
        """A tela lê os mesmos campos; o filtro muda o que eles significam."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        resposta = self.client.get(f"/api/investimentos/ativos/?carteira={self.inter.id}")

        self.assertEqual(len(resposta.data), 1)
        self.assertEqual(Decimal(resposta.data[0]["quantidade"]), Decimal("50"))
        self.assertEqual(Decimal(resposta.data[0]["preco_medio"]), Decimal("40.0000"))

    def test_listagem_sem_filtro_reporta_o_consolidado(self):
        """Sem `?carteira=`, o número é o do CPF — o que se declara no IR."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        resposta = self.client.get("/api/investimentos/ativos/")

        self.assertEqual(len(resposta.data), 1)
        self.assertEqual(Decimal(resposta.data[0]["quantidade"]), Decimal("150"))

    def test_dashboard_filtrado_soma_apenas_a_carteira(self):
        """O KPI de total investido é o primeiro número que o usuário confere."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        filtrado = self.client.get(
            f"/api/investimentos/dashboard/?carteira={self.xp.id}"
        )
        consolidado = self.client.get("/api/investimentos/dashboard/")

        # O consolidado passa pelo preço médio de 4 casas do ativo; o filtrado lê a
        # posição direto. A tolerância de um centavo cobre essa diferença de campo.
        self.assertAlmostEqual(filtrado.data["total_investido"], 3000.0, places=2)
        self.assertAlmostEqual(consolidado.data["total_investido"], 5000.0, delta=0.01)

    def test_dashboard_expoe_a_alocacao_por_carteira(self):
        """A resposta nova: quanto há em cada corretora."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        resposta = self.client.get("/api/investimentos/dashboard/")

        alocacao = dict(
            zip(
                resposta.data["alocacao_carteiras"]["labels"],
                resposta.data["alocacao_carteiras"]["valores"],
            )
        )
        self.assertEqual(alocacao, {"XP": 3000.0, "Inter": 2000.0})


class TickerDuplicadoTests(CarteiraBaseTestCase):
    """Querer o mesmo papel em duas corretoras leva a recadastrá-lo. Não é o caminho."""

    def test_recadastrar_o_mesmo_ticker_devolve_400_e_nao_500(self):
        """A colisão precisa virar erro de validação, não estouro no banco.

        O `unique_together` do modelo não vira validador do DRF porque `usuario` não
        está entre os campos do serializer. Sem a checagem explícita, o insert falha
        no Postgres e a resposta é um 500 opaco, bem no caminho mais provável de quem
        acabou de criar a segunda carteira.
        """
        resposta = self.client.post(
            "/api/investimentos/ativos/",
            {"ticker": "PETR4", "nome": "Petrobras", "carteira": self.inter.id},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ticker", resposta.data)

    def test_a_mensagem_aponta_o_caminho_certo(self):
        """Recusar sem dizer o que fazer deixaria o usuário sem saída."""
        resposta = self.client.post(
            "/api/investimentos/ativos/",
            {"ticker": "PETR4", "nome": "Petrobras"},
            format="json",
        )

        self.assertIn("ordem de compra", str(resposta.data["ticker"]))

    def test_editar_o_proprio_ativo_nao_colide_consigo_mesmo(self):
        """Salvar sem mudar o ticker não pode ser lido como duplicata."""
        resposta = self.client.patch(
            f"/api/investimentos/ativos/{self.ativo.id}/",
            {"ticker": "PETR4", "nome": "Petrobras S.A."},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_o_caminho_certo_funciona(self):
        """A alternativa que a mensagem indica precisa, de fato, resolver."""
        resposta = self.client.post(
            "/api/investimentos/transacoes/",
            {
                "ativo": self.ativo.id,
                "carteira": self.inter.id,
                "tipo": Transacao.TIPO_COMPRA,
                "data": timezone.localdate().isoformat(),
                "quantidade": "10",
                "preco_unitario": "20.00",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        posicao = PosicaoCarteira.objects.get(carteira=self.inter, ativo=self.ativo)
        self.assertEqual(posicao.quantidade, Decimal("10"))


class RentabilidadePorCarteiraTests(CarteiraBaseTestCase):
    """O KPI de lucro sob filtro precisa enxergar as pernas da transferência.

    Ignorá-las produzia lucro fantasma dos dois lados: a origem ficava com a compra
    mas sem o patrimônio, e o destino com o patrimônio mas sem custo. No consolidado
    as duas se anulavam, então o defeito só aparecia com filtro — exatamente onde a
    resposta importa.
    """

    def kpis(self, carteira=None) -> dict:
        """Lê o dashboard, opcionalmente escopado a uma carteira.

        Returns:
            dict: Payload do dashboard.
        """
        sufixo = f"?carteira={carteira.id}" if carteira else ""
        return self.client.get(f"/api/investimentos/dashboard/{sufixo}").data

    def transferir_tudo(self):
        """Compra 100 na XP e transfere as 100 para o Inter."""
        self.comprar(self.xp, 100, "30.00")
        self.client.post(
            "/api/investimentos/transacoes/transferir/",
            {
                "ativo": self.ativo.id, "origem": self.xp.id,
                "destino": self.inter.id, "quantidade": "100",
            },
            format="json",
        )

    def test_origem_nao_fica_com_prejuizo_fantasma(self):
        """Sem a correção, a XP mostrava perda do tamanho exato da transferência."""
        self.transferir_tudo()

        self.assertAlmostEqual(self.kpis(self.xp)["total_rentabilidade"], 0.0, delta=0.01)

    def test_destino_nao_fica_com_lucro_fantasma(self):
        """O papel chegou a custo: não houve ganho nenhum para exibir."""
        self.transferir_tudo()

        self.assertAlmostEqual(self.kpis(self.inter)["total_rentabilidade"], 0.0, delta=0.01)

    def test_a_soma_das_carteiras_bate_com_o_consolidado(self):
        """A invariante que revela o defeito: as partes têm de fechar com o todo."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")
        Cotacao.objects.create(
            ativo=self.ativo, data=timezone.localdate(), valor=Decimal("35.00")
        )
        self.client.post(
            "/api/investimentos/transacoes/transferir/",
            {
                "ativo": self.ativo.id, "origem": self.xp.id,
                "destino": self.inter.id, "quantidade": "40",
            },
            format="json",
        )

        soma = self.kpis(self.xp)["total_rentabilidade"] + self.kpis(self.inter)["total_rentabilidade"]

        self.assertAlmostEqual(soma, self.kpis()["total_rentabilidade"], delta=0.01)

    def test_o_consolidado_nao_muda_por_causa_da_transferencia(self):
        """Mudar de corretora não pode alterar o lucro total nem a rentabilidade."""
        self.comprar(self.xp, 100, "30.00")
        Cotacao.objects.create(
            ativo=self.ativo, data=timezone.localdate(), valor=Decimal("35.00")
        )
        antes = self.kpis()

        self.client.post(
            "/api/investimentos/transacoes/transferir/",
            {
                "ativo": self.ativo.id, "origem": self.xp.id,
                "destino": self.inter.id, "quantidade": "40",
            },
            format="json",
        )
        depois = self.kpis()

        self.assertAlmostEqual(
            antes["total_rentabilidade"], depois["total_rentabilidade"], delta=0.01
        )
        self.assertAlmostEqual(
            antes["total_rentabilidade_percentual"],
            depois["total_rentabilidade_percentual"],
            delta=0.01,
        )


class ContratoDaAPITests(CarteiraBaseTestCase):
    """Trava o contrato que o frontend passou a consumir.

    Cada teste aqui corresponde a um dado que uma tela lê hoje. Sem eles, remover um
    campo do serializer quebraria a tela sem nada acusar — foi exatamente assim que a
    coluna "Meta Alvo" do balanceamento passou meses renderizando vazio.
    """

    def test_carteira_expoe_o_valor_investido(self):
        """A tela de Carteiras responde "quanto tenho aqui" — antes só tinha a contagem."""
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        resposta = self.client.get("/api/investimentos/carteiras/")
        por_nome = {c["nome"]: c for c in resposta.data}

        self.assertAlmostEqual(por_nome["XP"]["valor_investido"], 3000.0, delta=0.01)
        self.assertAlmostEqual(por_nome["Inter"]["valor_investido"], 2000.0, delta=0.01)

    def test_listar_carteiras_nao_multiplica_consultas(self):
        """O custo da listagem não pode crescer com o número de carteiras.

        Valor, contagem de ativos e `pode_excluir` são anotados no queryset. Em
        `SerializerMethodField` cada um faria a sua consulta por carteira, e ninguém
        notaria até a lista ficar lenta em produção. O teste compara duas listagens
        com quantidades diferentes de carteira, em vez de fixar um número mágico.
        """
        self.comprar(self.xp, 100, "30.00")
        self.comprar(self.inter, 50, "40.00")

        with self.assertNumQueries(2):
            self.client.get("/api/investimentos/carteiras/")

        for i in range(4):
            Carteira.objects.create(usuario=self.user, nome=f"Corretora {i}")

        with self.assertNumQueries(2):
            self.client.get("/api/investimentos/carteiras/")

    def test_carteira_invalida_devolve_400(self):
        """`?carteira=abc` respondia o consolidado com 200 — um typo virava dado válido."""
        resposta = self.client.get("/api/investimentos/ativos/?carteira=abc")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("carteira", resposta.data)

    def test_carteira_de_outro_usuario_devolve_vazio_e_nao_400(self):
        """O isolamento não pode virar oráculo: 400/404 confirmaria que o id existe."""
        outro = User.objects.create_user(
            username="dono-alheio", password="senha-bem-comprida-123"
        )
        alheia = Carteira.objects.get(usuario=outro)

        resposta = self.client.get(f"/api/investimentos/ativos/?carteira={alheia.id}")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data), 0)

    def test_posicoes_filtram_por_ativo(self):
        """Sem `?ativo=`, o detalhe do ativo baixava as posições de todos os ativos."""
        outro_ativo = Ativo.objects.create(
            usuario=self.user, ticker="VALE3", nome="Vale"
        )
        self.comprar(self.xp, 100, "30.00")
        Transacao.objects.create(
            usuario=self.user, ativo=outro_ativo, carteira=self.xp,
            tipo=Transacao.TIPO_COMPRA, data=timezone.localdate(),
            quantidade=Decimal("10"), preco_unitario=Decimal("60.00"),
            valor_total=Decimal("600.00"),
        )

        resposta = self.client.get(f"/api/investimentos/posicoes/?ativo={self.ativo.id}")

        self.assertEqual(len(resposta.data), 1)
        self.assertEqual(resposta.data[0]["ativo"], self.ativo.id)

    def test_posicoes_por_ativo_nao_vazam_de_outro_usuario(self):
        """O filtro entra depois do isolamento, nunca no lugar dele."""
        outro = User.objects.create_user(
            username="investidor-alheio", password="senha-bem-comprida-123"
        )
        ativo_alheio = Ativo.objects.create(usuario=outro, ticker="ITUB4", nome="Itaú")
        Transacao.objects.create(
            usuario=outro, ativo=ativo_alheio, carteira=Carteira.padrao_de(outro),
            tipo=Transacao.TIPO_COMPRA, data=timezone.localdate(),
            quantidade=Decimal("5"), preco_unitario=Decimal("30.00"),
            valor_total=Decimal("150.00"),
        )

        resposta = self.client.get(f"/api/investimentos/posicoes/?ativo={ativo_alheio.id}")

        self.assertEqual(len(resposta.data), 0)

    def test_ativo_emite_meta_e_carteira_mesmo_no_consolidado(self):
        """Omitir a chave fazia quem somasse `meta_porcentagem` receber zero calado."""
        self.comprar(self.xp, 100, "30.00")

        resposta = self.client.get("/api/investimentos/ativos/")

        linha = resposta.data[0]
        self.assertIn("meta_porcentagem", linha)
        self.assertIn("carteira", linha)
        self.assertIsNone(linha["meta_porcentagem"])
        self.assertIsNone(linha["carteira"])

    def test_dashboard_nao_carrega_mais_os_blocos_orfaos(self):
        """Sete blocos serializados que nenhuma tela lia — quatro deles com 30 cotações por ativo."""
        self.comprar(self.xp, 100, "30.00")

        payload = self.client.get("/api/investimentos/dashboard/").data

        for orfao in [
            "ativos", "top_5_ativos", "top_rentabilidade", "ultima_transacao",
            "proximos_vencimentos", "alocacao_classes", "performance_yearly",
        ]:
            self.assertNotIn(orfao, payload, f"{orfao} voltou ao payload sem uma tela que o use")

    def test_dashboard_mantem_o_que_a_tela_consome(self):
        """A contrapartida do teste acima: enxugar não pode levar o que é lido."""
        self.comprar(self.xp, 100, "30.00")

        payload = self.client.get("/api/investimentos/dashboard/").data

        for usado in [
            "total_patrimonio", "total_investido", "total_rentabilidade",
            "total_rentabilidade_percentual", "total_dividendos",
            "alocacao_categorias", "alocacao_carteiras", "carteira_filtrada",
            "performance_monthly", "rentabilidade_mensal",
        ]:
            self.assertIn(usado, payload)

    def test_plano_entre_carteiras_traz_os_campos_que_a_tabela_mostra(self):
        """A coluna "Meta Alvo" lia `meta`, e o payload manda `meta_porcentagem`."""
        self.comprar(self.xp, 100, "30.00")

        payload = self.client.get("/api/investimentos/balanceamento/").data

        linha = payload["carteiras"][0]
        for campo in ["meta_porcentagem", "valor_atual", "perc_atual", "valor_ideal", "diferenca"]:
            self.assertIn(campo, linha)

    def test_meta_por_carteira_e_gravavel_pela_api(self):
        """O write-path existia inteiro no backend e nenhuma tela o usava."""
        resposta = self.client.post(
            "/api/investimentos/balanceamento/",
            {"carteiras": [{"id": self.xp.id, "meta": 60}, {"id": self.inter.id, "meta": 40}]},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.xp.refresh_from_db()
        self.inter.refresh_from_db()
        self.assertEqual(self.xp.meta_porcentagem, Decimal("60.00"))
        self.assertEqual(self.inter.meta_porcentagem, Decimal("40.00"))
