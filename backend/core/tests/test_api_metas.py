"""
Testes da API de Metas Financeiras.

Cobre o isolamento multi-tenant, a geração idempotente das metas padrão, o
registro de aportes e o cálculo das médias mensais sugeridas — incluindo o caso
crítico de compras de cartão, que não podem ser contadas junto com a fatura.
"""

from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from core.models import AporteMeta, CartaoCredito, Conta, MetaFinanceira, PlanoMetas
from core.services import metas_service
from investimento.models import Ativo, Cotacao, Transacao

User = get_user_model()


class MetasBaseAPITestCase(APITestCase):
    """Base compartilhada: cria o usuário autenticado e o cabeçalho JWT."""

    def setUp(self):
        self.user = User.objects.create_user(username="chrystian", password="senha-forte-123")
        self.token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def _criar_plano(self, renda="8000.00", custo="5000.00"):
        """Cria (ou atualiza) o plano do usuário de teste.

        Args:
            renda (str): Renda mensal de referência.
            custo (str): Custo de vida mensal de referência.

        Returns:
            PlanoMetas: O plano persistido.
        """
        plano, _ = PlanoMetas.objects.update_or_create(
            usuario=self.user,
            defaults={"renda_mensal": Decimal(renda), "custo_vida_mensal": Decimal(custo)},
        )
        return plano


class GerarMetasPadraoAPITests(MetasBaseAPITestCase):
    """Verifica a materialização das quatro metas derivadas dos múltiplos."""

    def test_gera_as_quatro_metas_com_os_multiplicadores_corretos(self):
        self._criar_plano(renda="8000.00", custo="5000.00")

        response = self.client.post("/api/financeiro/metas/gerar-padrao/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

        alvos = {m["tipo"]: Decimal(m["valor_alvo"]) for m in response.data}
        # renda x 200
        self.assertEqual(alvos[MetaFinanceira.TIPO_PATRIMONIO_RENDA], Decimal("1600000.00"))
        # renda x 0,1
        self.assertEqual(alvos[MetaFinanceira.TIPO_APORTE_MENSAL], Decimal("800.00"))
        # custo de vida x 6
        self.assertEqual(alvos[MetaFinanceira.TIPO_RESERVA_EMERGENCIA], Decimal("30000.00"))
        # renda x 0,6
        self.assertEqual(alvos[MetaFinanceira.TIPO_GASTO_ESSENCIAL], Decimal("4800.00"))

    def test_reproduz_o_exemplo_de_referencia_com_centavos(self):
        """Trava os arredondamentos usando um caso real com centavos."""
        self._criar_plano(renda="8093.68", custo="6266.57")

        self.client.post("/api/financeiro/metas/gerar-padrao/")
        alvos = {
            m.tipo: m.valor_alvo for m in MetaFinanceira.objects.filter(usuario=self.user)
        }

        self.assertEqual(alvos[MetaFinanceira.TIPO_PATRIMONIO_RENDA], Decimal("1618736.00"))
        self.assertEqual(alvos[MetaFinanceira.TIPO_APORTE_MENSAL], Decimal("809.37"))
        self.assertEqual(alvos[MetaFinanceira.TIPO_RESERVA_EMERGENCIA], Decimal("37599.42"))
        self.assertEqual(alvos[MetaFinanceira.TIPO_GASTO_ESSENCIAL], Decimal("4856.21"))

    def test_meta_de_gasto_essencial_tem_natureza_de_teto(self):
        self._criar_plano()
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta = MetaFinanceira.objects.get(
            usuario=self.user, tipo=MetaFinanceira.TIPO_GASTO_ESSENCIAL
        )
        self.assertEqual(meta.natureza, MetaFinanceira.NATUREZA_TETO)

        # As demais acumulam em direção ao alvo.
        outras = MetaFinanceira.objects.filter(usuario=self.user).exclude(pk=meta.pk)
        for outra in outras:
            self.assertEqual(outra.natureza, MetaFinanceira.NATUREZA_ACUMULO)

    def test_regerar_recalcula_alvo_sem_zerar_o_acumulado(self):
        self._criar_plano(renda="8000.00", custo="5000.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta = MetaFinanceira.objects.get(
            usuario=self.user, tipo=MetaFinanceira.TIPO_RESERVA_EMERGENCIA
        )
        meta.valor_acumulado = Decimal("12000.00")
        meta.prazo = timezone.localdate()
        meta.save()

        # Usuário revisa o custo de vida para cima e manda recalcular.
        self._criar_plano(renda="8000.00", custo="6000.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta.refresh_from_db()
        self.assertEqual(meta.valor_alvo, Decimal("36000.00"))
        self.assertEqual(meta.valor_acumulado, Decimal("12000.00"))
        self.assertIsNotNone(meta.prazo)

    def test_e_idempotente_e_nao_duplica_metas(self):
        self._criar_plano()
        self.client.post("/api/financeiro/metas/gerar-padrao/")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        self.assertEqual(MetaFinanceira.objects.filter(usuario=self.user).count(), 4)

    def test_recusa_gerar_sem_base_de_calculo_preenchida(self):
        response = self.client.post("/api/financeiro/metas/gerar-padrao/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MetaFinanceira.objects.filter(usuario=self.user).count(), 0)


class MultiplicadoresAPITests(MetasBaseAPITestCase):
    """Verifica a edição dos fatores que derivam os alvos das metas padrão."""

    def setUp(self):
        super().setUp()
        self._criar_plano(renda="8000.00", custo="5000.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

    def _meta(self, tipo):
        return MetaFinanceira.objects.get(usuario=self.user, tipo=tipo)

    def test_editar_multiplicador_recalcula_o_alvo(self):
        response = self.client.put(
            "/api/financeiro/metas/multiplicadores/",
            {"patrimonio_renda": "150", "reserva_emergencia": "12"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 8.000 x 150
        self.assertEqual(
            self._meta(MetaFinanceira.TIPO_PATRIMONIO_RENDA).valor_alvo, Decimal("1200000.00")
        )
        # 5.000 x 12
        self.assertEqual(
            self._meta(MetaFinanceira.TIPO_RESERVA_EMERGENCIA).valor_alvo, Decimal("60000.00")
        )
        # As não enviadas ficam intactas.
        self.assertEqual(
            self._meta(MetaFinanceira.TIPO_GASTO_ESSENCIAL).multiplicador, Decimal("0.6000")
        )

    def test_recalcular_metas_preserva_multiplicador_editado(self):
        """Regressão: recalcular não pode desfazer o fator escolhido pelo usuário."""
        self.client.put(
            "/api/financeiro/metas/multiplicadores/", {"patrimonio_renda": "150"}, format="json"
        )

        # Usuário revisa a renda e manda recalcular.
        self._criar_plano(renda="10000.00", custo="5000.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta = self._meta(MetaFinanceira.TIPO_PATRIMONIO_RENDA)
        self.assertEqual(meta.multiplicador, Decimal("150.0000"))
        self.assertEqual(meta.valor_alvo, Decimal("1500000.00"))  # 10.000 x 150, não x 200

    def test_recalcular_preserva_nome_e_observacao_personalizados(self):
        meta = self._meta(MetaFinanceira.TIPO_RESERVA_EMERGENCIA)
        self.client.patch(
            f"/api/financeiro/metas/{meta.id}/",
            {"nome": "Meu colchão", "observacao": "No CDB de liquidez diária"},
            format="json",
        )

        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta.refresh_from_db()
        self.assertEqual(meta.nome, "Meu colchão")
        self.assertEqual(meta.observacao, "No CDB de liquidez diária")

    def test_patch_do_multiplicador_tambem_recalcula_o_alvo(self):
        meta = self._meta(MetaFinanceira.TIPO_GASTO_ESSENCIAL)

        response = self.client.patch(
            f"/api/financeiro/metas/{meta.id}/", {"multiplicador": "0.5"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meta.refresh_from_db()
        self.assertEqual(meta.valor_alvo, Decimal("4000.00"))  # 8.000 x 0,5

    def test_recusa_multiplicador_nao_positivo(self):
        response = self.client.put(
            "/api/financeiro/metas/multiplicadores/", {"patrimonio_renda": "0"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("patrimonio_renda", response.data)
        # Nada foi gravado.
        self.assertEqual(
            self._meta(MetaFinanceira.TIPO_PATRIMONIO_RENDA).multiplicador, Decimal("200.0000")
        )

    def test_recusa_valor_nao_numerico_sem_gravar_os_demais(self):
        response = self.client.put(
            "/api/financeiro/metas/multiplicadores/",
            {"patrimonio_renda": "150", "reserva_emergencia": "abc"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # O lote é atômico: o fator válido não pode ter sido aplicado sozinho.
        self.assertEqual(
            self._meta(MetaFinanceira.TIPO_PATRIMONIO_RENDA).multiplicador, Decimal("200.0000")
        )

    def test_expoe_os_multiplicadores_padrao_para_restaurar(self):
        response = self.client.get("/api/financeiro/metas-plano/")

        padroes = response.data["multiplicadores_padrao"]
        self.assertEqual(Decimal(padroes[MetaFinanceira.TIPO_PATRIMONIO_RENDA]), Decimal("200"))
        self.assertEqual(Decimal(padroes[MetaFinanceira.TIPO_APORTE_MENSAL]), Decimal("0.1"))
        self.assertEqual(Decimal(padroes[MetaFinanceira.TIPO_RESERVA_EMERGENCIA]), Decimal("6"))
        self.assertEqual(Decimal(padroes[MetaFinanceira.TIPO_GASTO_ESSENCIAL]), Decimal("0.6"))

    def test_nao_altera_multiplicador_de_meta_de_outro_usuario(self):
        outro = User.objects.create_user(username="alheio", password="senha-forte-123")
        meta_alheia = MetaFinanceira.objects.create(
            usuario=outro, nome="Patrimônio alheio", tipo=MetaFinanceira.TIPO_PATRIMONIO_RENDA,
            base_calculo=MetaFinanceira.BASE_RENDA, multiplicador=Decimal("200"),
            valor_alvo=Decimal("100.00"),
        )

        self.client.put(
            "/api/financeiro/metas/multiplicadores/", {"patrimonio_renda": "150"}, format="json"
        )

        meta_alheia.refresh_from_db()
        self.assertEqual(meta_alheia.multiplicador, Decimal("200.0000"))


class AporteMetaAPITests(MetasBaseAPITestCase):
    """Verifica o registro de aportes e a soma no valor acumulado."""

    def setUp(self):
        super().setUp()
        self.meta = MetaFinanceira.objects.create(
            usuario=self.user,
            nome="Reserva de emergência",
            tipo=MetaFinanceira.TIPO_RESERVA_EMERGENCIA,
            valor_alvo=Decimal("30000.00"),
            valor_acumulado=Decimal("1000.00"),
        )

    def test_aporte_soma_no_acumulado_e_grava_historico(self):
        response = self.client.post(
            f"/api/financeiro/metas/{self.meta.id}/aportes/",
            {"valor": "500.00", "data": "2026-01-15", "observacao": "13º salário"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_acumulado, Decimal("1500.00"))
        self.assertEqual(AporteMeta.objects.filter(meta=self.meta).count(), 1)
        # O histórico volta na própria resposta, evitando um segundo GET na tela.
        self.assertEqual(len(response.data["aportes"]), 1)

    def test_aportes_sucessivos_acumulam(self):
        for _ in range(3):
            self.client.post(
                f"/api/financeiro/metas/{self.meta.id}/aportes/",
                {"valor": "250.00"},
                format="json",
            )

        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_acumulado, Decimal("1750.00"))

    def test_excluir_aporte_desconta_do_acumulado(self):
        criado = self.client.post(
            f"/api/financeiro/metas/{self.meta.id}/aportes/",
            {"valor": "500.00"},
            format="json",
        )
        aporte_id = criado.data["aportes"][0]["id"]

        response = self.client.delete(
            f"/api/financeiro/metas/{self.meta.id}/aportes/{aporte_id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_acumulado, Decimal("1000.00"))
        self.assertEqual(AporteMeta.objects.filter(meta=self.meta).count(), 0)
        self.assertEqual(len(response.data["aportes"]), 0)

    def test_excluir_aporte_nao_deixa_acumulado_negativo(self):
        criado = self.client.post(
            f"/api/financeiro/metas/{self.meta.id}/aportes/",
            {"valor": "500.00"},
            format="json",
        )
        aporte_id = criado.data["aportes"][0]["id"]

        # Usuário zera o acumulado manualmente antes de excluir o aporte.
        self.client.patch(
            f"/api/financeiro/metas/{self.meta.id}/",
            {"valor_acumulado": "0"},
            format="json",
        )
        self.client.delete(f"/api/financeiro/metas/{self.meta.id}/aportes/{aporte_id}/")

        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_acumulado, Decimal("0.00"))

    def test_nao_exclui_aporte_de_outra_meta(self):
        outra = MetaFinanceira.objects.create(
            usuario=self.user, nome="Compra de celular", valor_alvo=Decimal("5000.00")
        )
        criado = self.client.post(
            f"/api/financeiro/metas/{outra.id}/aportes/", {"valor": "300.00"}, format="json"
        )
        aporte_id = criado.data["aportes"][0]["id"]

        # Tenta excluir pela meta errada.
        response = self.client.delete(
            f"/api/financeiro/metas/{self.meta.id}/aportes/{aporte_id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        outra.refresh_from_db()
        self.assertEqual(outra.valor_acumulado, Decimal("300.00"))

    def test_recusa_aporte_com_valor_nao_positivo(self):
        response = self.client.post(
            f"/api/financeiro/metas/{self.meta.id}/aportes/",
            {"valor": "0"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_acumulado, Decimal("1000.00"))


class ProgressoPelaCarteiraAPITests(MetasBaseAPITestCase):
    """Verifica as metas cujo progresso vem do valor de mercado da carteira."""

    def _criar_ativo(self, ticker, quantidade, preco_medio, cotacao=None):
        """Cria um ativo e, opcionalmente, sua cotação mais recente.

        Args:
            ticker (str): Código do ativo.
            quantidade (str): Quantidade em custódia.
            preco_medio (str): Preço médio de aquisição.
            cotacao (str | None): Cotação atual; None deixa o ativo sem cotação.

        Returns:
            Ativo: O ativo criado.
        """
        ativo = Ativo.objects.create(
            usuario=self.user,
            ticker=ticker,
            nome=ticker,
            quantidade=Decimal(quantidade),
            preco_medio=Decimal(preco_medio),
        )
        if cotacao is not None:
            Cotacao.objects.create(
                ativo=ativo, data=timezone.localdate(), valor=Decimal(cotacao)
            )
        return ativo

    def test_metas_de_investimento_nascem_lendo_a_carteira(self):
        self._criar_plano()
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        origens = {
            m.tipo: m.origem_acumulado for m in MetaFinanceira.objects.filter(usuario=self.user)
        }
        # Patrimônio é alvo de longo prazo: lê o valor de mercado acumulado.
        self.assertEqual(
            origens[MetaFinanceira.TIPO_PATRIMONIO_RENDA], MetaFinanceira.ORIGEM_CARTEIRA
        )
        # A meta mensal se renova todo mês: lê só os aportes da competência.
        self.assertEqual(
            origens[MetaFinanceira.TIPO_APORTE_MENSAL], MetaFinanceira.ORIGEM_APORTES_MES
        )
        # Reserva e teto de gastos não têm relação com a carteira.
        self.assertEqual(
            origens[MetaFinanceira.TIPO_RESERVA_EMERGENCIA], MetaFinanceira.ORIGEM_MANUAL
        )
        self.assertEqual(
            origens[MetaFinanceira.TIPO_GASTO_ESSENCIAL], MetaFinanceira.ORIGEM_MANUAL
        )

    def test_usa_a_cotacao_mais_recente_e_cai_no_preco_medio_sem_cotacao(self):
        self._criar_ativo("PETR4", "100", "30.00", cotacao="38.50")   # 3.850,00 a mercado
        self._criar_ativo("SEMCOT", "10", "12.00")                     # 120,00 pelo preço médio

        self.assertEqual(metas_service.patrimonio_carteira(self.user), Decimal("3970.00"))

    def test_cotacao_mais_recente_prevalece_sobre_a_antiga(self):
        ativo = self._criar_ativo("VALE3", "50", "60.00", cotacao="70.00")
        Cotacao.objects.create(
            ativo=ativo,
            data=timezone.localdate() - relativedelta(days=5),
            valor=Decimal("10.00"),
        )

        self.assertEqual(metas_service.patrimonio_carteira(self.user), Decimal("3500.00"))

    def test_ativos_inativos_ficam_de_fora(self):
        ativo = self._criar_ativo("XPTO3", "100", "10.00", cotacao="20.00")
        ativo.ativo = False
        ativo.save()

        self.assertEqual(metas_service.patrimonio_carteira(self.user), Decimal("0.00"))

    def test_api_reporta_progresso_a_partir_do_valor_de_mercado(self):
        self._criar_ativo("PETR4", "100", "30.00", cotacao="38.50")  # 3.850,00
        self._criar_plano(renda="8000.00", custo="5000.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        response = self.client.get("/api/financeiro/metas/")
        metas = {m["tipo"]: m for m in response.data}

        # Patrimônio: alvo 1.600.000,00 e carteira de 3.850,00.
        patrimonio = metas[MetaFinanceira.TIPO_PATRIMONIO_RENDA]
        self.assertEqual(patrimonio["valor_acumulado_efetivo"], 3850.00)
        self.assertEqual(patrimonio["progresso_percentual"], 0.24)
        self.assertEqual(patrimonio["valor_restante"], 1596150.00)
        # O campo manual continua zerado — o efetivo é que vem da carteira.
        self.assertEqual(Decimal(patrimonio["valor_acumulado"]), Decimal("0.00"))

        # Meta de reserva segue manual, indiferente à carteira.
        reserva = metas[MetaFinanceira.TIPO_RESERVA_EMERGENCIA]
        self.assertEqual(reserva["valor_acumulado_efetivo"], 0.0)


class MetaMensalAPITests(MetasBaseAPITestCase):
    """Verifica a meta mensal, cujo progresso são os aportes da competência."""

    def _criar_compra(self, valor, data=None, tipo=None):
        """Registra uma ordem na carteira do usuário de teste.

        Args:
            valor (str): Valor total da ordem.
            data (date | None): Data da ordem; None usa hoje.
            tipo (str | None): Tipo da transação; None usa compra.

        Returns:
            Transacao: A ordem criada.
        """
        ativo, _ = Ativo.objects.get_or_create(
            usuario=self.user,
            ticker="PETR4",
            defaults={"nome": "Petrobras", "quantidade": Decimal("0"), "preco_medio": Decimal("0")},
        )
        return Transacao.objects.create(
            usuario=self.user,
            ativo=ativo,
            tipo=tipo or Transacao.TIPO_COMPRA,
            data=data or timezone.localdate(),
            quantidade=Decimal("1"),
            preco_unitario=Decimal(valor),
            valor_total=Decimal(valor),
        )

    def test_soma_apenas_as_compras_da_competencia_atual(self):
        self._criar_compra("300.00")
        self._criar_compra("200.00")
        # Compra do mês passado não conta para a meta deste mês.
        self._criar_compra("999.00", data=timezone.localdate().replace(day=1) - relativedelta(days=1))

        self.assertEqual(metas_service.aportes_do_mes(self.user), Decimal("500.00"))

    def test_vendas_e_proventos_nao_contam_como_aporte(self):
        self._criar_compra("400.00")
        self._criar_compra("1000.00", tipo=Transacao.TIPO_VENDA)
        self._criar_compra("50.00", tipo=Transacao.TIPO_DIVIDENDO)

        self.assertEqual(metas_service.aportes_do_mes(self.user), Decimal("400.00"))

    def test_progresso_compara_aportes_do_mes_com_o_alvo_mensal(self):
        self._criar_plano(renda="8000.00", custo="5000.00")  # alvo mensal = 800,00
        self._criar_compra("600.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        response = self.client.get("/api/financeiro/metas/")
        mensal = next(m for m in response.data if m["tipo"] == MetaFinanceira.TIPO_APORTE_MENSAL)

        self.assertEqual(mensal["nome"], "Meta mensal investimento")
        self.assertEqual(Decimal(mensal["valor_alvo"]), Decimal("800.00"))
        self.assertEqual(mensal["valor_acumulado_efetivo"], 600.00)
        self.assertEqual(mensal["progresso_percentual"], 75.0)
        self.assertEqual(mensal["valor_restante"], 200.00)

    def test_patrimonio_da_carteira_nao_infla_a_meta_mensal(self):
        """Regressão: o alvo mensal não pode ser comparado ao patrimônio total."""
        Ativo.objects.create(
            usuario=self.user,
            ticker="ANTIGO3",
            nome="Posição antiga",
            quantidade=Decimal("1000"),
            preco_medio=Decimal("50.00"),
        )
        self._criar_plano(renda="8000.00", custo="5000.00")
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        response = self.client.get("/api/financeiro/metas/")
        mensal = next(m for m in response.data if m["tipo"] == MetaFinanceira.TIPO_APORTE_MENSAL)

        # 50.000,00 de patrimônio, mas nenhum aporte neste mês.
        self.assertEqual(mensal["valor_acumulado_efetivo"], 0.0)
        self.assertEqual(mensal["progresso_percentual"], 0.0)

    def test_aportes_de_outro_usuario_nao_contam(self):
        outro = User.objects.create_user(username="outro-investidor", password="senha-forte-123")
        ativo = Ativo.objects.create(
            usuario=outro, ticker="ALHEIO3", nome="Alheio",
            quantidade=Decimal("1"), preco_medio=Decimal("1"),
        )
        Transacao.objects.create(
            usuario=outro, ativo=ativo, tipo=Transacao.TIPO_COMPRA,
            data=timezone.localdate(), quantidade=Decimal("1"),
            preco_unitario=Decimal("5000.00"), valor_total=Decimal("5000.00"),
        )

        self.assertEqual(metas_service.aportes_do_mes(self.user), Decimal("0.00"))

    def test_regerar_metas_respeita_troca_para_manual(self):
        self._criar_plano()
        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta = MetaFinanceira.objects.get(
            usuario=self.user, tipo=MetaFinanceira.TIPO_PATRIMONIO_RENDA
        )
        self.client.patch(
            f"/api/financeiro/metas/{meta.id}/",
            {"origem_acumulado": "manual"},
            format="json",
        )

        self.client.post("/api/financeiro/metas/gerar-padrao/")

        meta.refresh_from_db()
        self.assertEqual(meta.origem_acumulado, MetaFinanceira.ORIGEM_MANUAL)

    def test_carteira_de_outro_usuario_nao_vaza_no_progresso(self):
        outro = User.objects.create_user(username="outro", password="senha-forte-123")
        Ativo.objects.create(
            usuario=outro,
            ticker="ALHEIO3",
            nome="Alheio",
            quantidade=Decimal("1000"),
            preco_medio=Decimal("100.00"),
        )

        self.assertEqual(metas_service.patrimonio_carteira(self.user), Decimal("0.00"))


class MigracoesDeDadosMetasTests(MetasBaseAPITestCase):
    """Verifica as migrations que convertem metas criadas em versões anteriores.

    Usa os literais antigos de propósito: são o estado real das linhas no banco
    de quem já usava a tela, e não devem seguir eventuais renomeações futuras
    das constantes do modelo.
    """

    def _rodar(self, modulo, funcao):
        """Executa uma função de migration contra o registro de apps atual.

        Args:
            modulo (str): Caminho do módulo da migration.
            funcao (str): Nome da função a executar.
        """
        from importlib import import_module
        from django.apps import apps as global_apps

        getattr(import_module(modulo), funcao)(global_apps, None)

    def test_0004_aponta_metas_de_investimento_antigas_para_a_carteira(self):
        """Metas criadas antes do campo `origem_acumulado` devem ser convertidas.

        Elas nasceram com o default 'manual' porque o campo ainda não existia —
        não há escolha do usuário a preservar nessas linhas.
        """
        patrimonio = MetaFinanceira.objects.create(
            usuario=self.user, nome="Patrimônio antigo", tipo="patrimonio_renda",
            valor_alvo=Decimal("1000.00"), origem_acumulado="manual",
        )
        inicial = MetaFinanceira.objects.create(
            usuario=self.user, nome="Meta inicial de investimentos",
            tipo="investimento_inicial", valor_alvo=Decimal("800.00"),
            origem_acumulado="manual",
        )
        reserva = MetaFinanceira.objects.create(
            usuario=self.user, nome="Reserva antiga", tipo="reserva_emergencia",
            valor_alvo=Decimal("30000.00"), origem_acumulado="manual",
        )

        self._rodar(
            "core.migrations.0004_backfill_origem_acumulado_carteira",
            "marcar_origem_carteira",
        )

        patrimonio.refresh_from_db()
        inicial.refresh_from_db()
        reserva.refresh_from_db()
        self.assertEqual(patrimonio.origem_acumulado, "carteira")
        self.assertEqual(inicial.origem_acumulado, "carteira")
        # Reserva de emergência não é carteira e deve permanecer manual.
        self.assertEqual(reserva.origem_acumulado, "manual")

    def test_0006_converte_meta_inicial_em_meta_mensal(self):
        antiga = MetaFinanceira.objects.create(
            usuario=self.user, nome="Meta inicial de investimentos",
            tipo="investimento_inicial", valor_alvo=Decimal("809.37"),
            origem_acumulado="carteira",
        )

        self._rodar(
            "core.migrations.0006_renomear_meta_inicial_para_meta_mensal",
            "para_meta_mensal",
        )

        antiga.refresh_from_db()
        self.assertEqual(antiga.tipo, MetaFinanceira.TIPO_APORTE_MENSAL)
        self.assertEqual(antiga.nome, "Meta mensal")
        # O ponto central: deixa de olhar o patrimônio total e passa a olhar o mês.
        self.assertEqual(antiga.origem_acumulado, MetaFinanceira.ORIGEM_APORTES_MES)
        self.assertEqual(antiga.valor_alvo, Decimal("809.37"))

    def test_0006_preserva_nome_personalizado_pelo_usuario(self):
        renomeada = MetaFinanceira.objects.create(
            usuario=self.user, nome="Meu aporte", tipo="investimento_inicial",
            valor_alvo=Decimal("800.00"), origem_acumulado="carteira",
        )

        self._rodar(
            "core.migrations.0006_renomear_meta_inicial_para_meta_mensal",
            "para_meta_mensal",
        )

        renomeada.refresh_from_db()
        self.assertEqual(renomeada.nome, "Meu aporte")
        self.assertEqual(renomeada.tipo, MetaFinanceira.TIPO_APORTE_MENSAL)


class MetaValidacaoAPITests(MetasBaseAPITestCase):
    """Verifica as validações de criação de metas personalizadas."""

    def test_recusa_valor_alvo_nao_positivo(self):
        response = self.client.post(
            "/api/financeiro/metas/",
            {"nome": "Viagem", "valor_alvo": "0", "base_calculo": "manual"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valor_alvo", response.data)

    def test_recusa_base_derivada_sem_multiplicador(self):
        response = self.client.post(
            "/api/financeiro/metas/",
            {"nome": "Meta derivada", "valor_alvo": "1000.00", "base_calculo": "renda"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("multiplicador", response.data)

    def test_cria_meta_personalizada_valida(self):
        response = self.client.post(
            "/api/financeiro/metas/",
            {"nome": "Troca de carro", "valor_alvo": "45000.00", "base_calculo": "manual"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        meta = MetaFinanceira.objects.get(usuario=self.user, nome="Troca de carro")
        self.assertEqual(meta.tipo, MetaFinanceira.TIPO_PERSONALIZADA)

    def test_fluxo_completo_de_meta_de_poupanca(self):
        """Cenário de uso: juntar R$ 5.000 para um celular, aporte a aporte."""
        criada = self.client.post(
            "/api/financeiro/metas/",
            {"nome": "Compra de celular", "valor_alvo": "5000.00", "base_calculo": "manual"},
            format="json",
        )
        meta_id = criada.data["id"]

        # Começa do zero, como o usuário vê no cartão.
        self.assertEqual(criada.data["valor_acumulado_efetivo"], 0.0)
        self.assertEqual(criada.data["progresso_percentual"], 0.0)
        self.assertEqual(criada.data["origem_acumulado"], MetaFinanceira.ORIGEM_MANUAL)

        for valor in ("1000.00", "500.00", "750.00"):
            resposta = self.client.post(
                f"/api/financeiro/metas/{meta_id}/aportes/", {"valor": valor}, format="json"
            )

        self.assertEqual(resposta.data["valor_acumulado_efetivo"], 2250.00)
        self.assertEqual(resposta.data["progresso_percentual"], 45.0)
        self.assertEqual(resposta.data["valor_restante"], 2750.00)
        self.assertEqual(len(resposta.data["aportes"]), 3)

        # Um dos aportes foi digitado errado e é removido.
        errado = resposta.data["aportes"][0]["id"]
        corrigida = self.client.delete(
            f"/api/financeiro/metas/{meta_id}/aportes/{errado}/"
        )

        self.assertEqual(len(corrigida.data["aportes"]), 2)
        self.assertEqual(
            corrigida.data["valor_acumulado_efetivo"],
            2250.00 - float(resposta.data["aportes"][0]["valor"]),
        )


class PlanoMetasAPITests(MetasBaseAPITestCase):
    """Verifica o endpoint da base de cálculo e suas sugestões automáticas."""

    def test_get_cria_plano_vazio_e_devolve_sugestoes(self):
        response = self.client.get("/api/financeiro/metas-plano/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("plano", response.data)
        self.assertIn("sugestoes", response.data)
        self.assertIn("gasto_essencial_mes", response.data)
        self.assertTrue(PlanoMetas.objects.filter(usuario=self.user).exists())

    def test_put_salva_a_base_de_calculo(self):
        response = self.client.put(
            "/api/financeiro/metas-plano/",
            {"renda_mensal": "9500.00", "custo_vida_mensal": "6100.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plano = PlanoMetas.objects.get(usuario=self.user)
        self.assertEqual(plano.renda_mensal, Decimal("9500.00"))
        self.assertEqual(plano.custo_vida_mensal, Decimal("6100.00"))

    def test_recusa_renda_negativa(self):
        response = self.client.put(
            "/api/financeiro/metas-plano/",
            {"renda_mensal": "-1.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MediasMensaisServiceTests(MetasBaseAPITestCase):
    """Verifica o cálculo das médias que alimentam as sugestões da tela."""

    def test_media_considera_a_janela_de_meses_informada(self):
        hoje = timezone.localdate()
        for offset in range(3):
            Conta.objects.create(
                usuario=self.user,
                tipo=Conta.TIPO_RECEITA,
                descricao=f"Salário {offset}",
                valor=Decimal("6000.00"),
                data_prevista=(hoje.replace(day=1) - relativedelta(months=offset)),
            )

        renda, _ = metas_service.medias_mensais(self.user, meses=3)
        self.assertEqual(renda, 6000.00)

        # Com janela de 1 mês só entra a competência corrente — mesmo valor aqui.
        renda_1m, _ = metas_service.medias_mensais(self.user, meses=1)
        self.assertEqual(renda_1m, 6000.00)

    def test_nao_conta_em_dobro_compra_de_cartao_e_fatura(self):
        hoje = timezone.localdate().replace(day=1)
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Nubank", ultimos_digitos="1234"
        )

        # Compra individual no cartão. O signal `monitorar_salvamento_conta`
        # consolida sozinho a fatura de R$ 400 para a mesma competência.
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Mercado no cartão",
            valor=Decimal("400.00"),
            data_prevista=hoje,
            cartao=cartao,
            eh_fatura_cartao=False,
        )
        self.assertTrue(
            Conta.objects.filter(
                usuario=self.user, cartao=cartao, eh_fatura_cartao=True, data_prevista=hoje
            ).exists(),
            "A fatura consolidada deveria ter sido criada pelo signal.",
        )

        # Despesa comum, fora do cartão.
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Aluguel",
            valor=Decimal("2000.00"),
            data_prevista=hoje,
        )

        _, custo = metas_service.medias_mensais(self.user, meses=1)

        # 2000 (aluguel) + 400 (fatura). A compra individual NÃO entra de novo.
        self.assertEqual(custo, 2400.00)


class MetasIsolamentoAPITests(APITestCase):
    """Garante que uma meta de um usuário é invisível para outro."""

    def setUp(self):
        self.maria = User.objects.create_user(username="maria", password="senha-forte-123")
        self.meta_maria = MetaFinanceira.objects.create(
            usuario=self.maria,
            nome="Reserva da Maria",
            valor_alvo=Decimal("30000.00"),
        )

        self.joao = User.objects.create_user(username="joao", password="senha-forte-123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.joao)}")

    def test_listagem_nao_expoe_meta_de_outro_usuario(self):
        response = self.client.get("/api/financeiro/metas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_detalhe_de_meta_alheia_retorna_404(self):
        response = self.client.get(f"/api/financeiro/metas/{self.meta_maria.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nao_pode_aportar_em_meta_alheia(self):
        response = self.client.post(
            f"/api/financeiro/metas/{self.meta_maria.id}/aportes/",
            {"valor": "100.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.meta_maria.refresh_from_db()
        self.assertEqual(self.meta_maria.valor_acumulado, Decimal("0"))

    def test_nao_pode_excluir_meta_alheia(self):
        response = self.client.delete(f"/api/financeiro/metas/{self.meta_maria.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MetaFinanceira.objects.filter(pk=self.meta_maria.pk).exists())
