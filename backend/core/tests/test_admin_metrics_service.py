"""Testes das métricas de plataforma do painel administrativo.

O endpoint já verifica formato e autorização; o que faltava era conferir os números
que sustentam as decisões tomadas a partir do painel. Três pontos concentram o
risco: a série de cadastros precisa incluir os dias sem cadastro (senão o gráfico
liga dois pontos distantes como se houvesse crescimento contínuo), o percentual não
pode dividir por zero (base vazia é o estado de toda instalação nova) e nenhum
valor financeiro pode aparecer.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import ConfigUsuario
from core.services.admin_metrics_service import coletar_metricas

User = get_user_model()


class ColetarMetricasTests(TestCase):
    """Verifica os indicadores agregados da plataforma."""

    def _criar(self, username: str, **campos):
        """Cria um usuário com config associada.

        Returns:
            User: A conta criada.
        """
        usuario = User.objects.create_user(
            username=username, password="senha-comprida-123", **campos
        )
        ConfigUsuario.objects.get_or_create(usuario=usuario)
        return usuario

    def test_base_vazia_nao_divide_por_zero(self):
        """Instalação sem nenhuma conta devolve zero, não erro."""
        metricas = coletar_metricas()

        self.assertEqual(metricas["contas"]["total"], 0)
        self.assertEqual(metricas["percentual_verificado"], 0.0)

    def test_conta_totais_por_situacao(self):
        """Ativas, suspensas e administradores são contados separadamente."""
        self._criar("joana", email="joana@exemplo.com")
        self._criar("admin", email="admin@exemplo.com", is_staff=True)
        suspensa = self._criar("pedro", email="pedro@exemplo.com")
        suspensa.is_active = False
        suspensa.save(update_fields=["is_active"])

        contas = coletar_metricas()["contas"]

        self.assertEqual(contas["total"], 3)
        self.assertEqual(contas["ativas"], 2)
        self.assertEqual(contas["suspensas"], 1)
        self.assertEqual(contas["administradores"], 1)

    def test_conta_apenas_quem_tem_email(self):
        """Contas sem endereço não entram em `com_email`."""
        self._criar("joana", email="joana@exemplo.com")
        self._criar("antiga")

        self.assertEqual(coletar_metricas()["contas"]["com_email"], 1)

    def test_percentual_verificado_sobre_o_total(self):
        """O percentual é calculado no servidor, com uma casa decimal."""
        verificada = self._criar("joana", email="joana@exemplo.com")
        verificada.config.email_verificado = True
        verificada.config.save(update_fields=["email_verificado"])
        self._criar("pedro", email="pedro@exemplo.com")
        self._criar("ana", email="ana@exemplo.com")

        metricas = coletar_metricas()

        self.assertEqual(metricas["contas"]["verificadas"], 1)
        self.assertEqual(metricas["percentual_verificado"], 33.3)

    def test_janela_de_cadastros_recentes(self):
        """`novas_7d` só conta o que entrou na janela."""
        self._criar("recente", email="recente@exemplo.com")
        antiga = self._criar("antiga", email="antiga@exemplo.com")
        antiga.date_joined = timezone.now() - timedelta(days=40)
        antiga.save(update_fields=["date_joined"])

        contas = coletar_metricas()["contas"]

        self.assertEqual(contas["novas_7d"], 1)
        self.assertEqual(contas["novas_30d"], 1)
        self.assertEqual(contas["total"], 2)

    def test_atividade_recente_usa_o_ultimo_acesso(self):
        """Quem nunca acessou é contado à parte, não como inativo recente."""
        ativa = self._criar("ativa", email="ativa@exemplo.com")
        ativa.last_login = timezone.now() - timedelta(days=2)
        ativa.save(update_fields=["last_login"])
        self._criar("nunca", email="nunca@exemplo.com")

        contas = coletar_metricas()["contas"]

        self.assertEqual(contas["ativos_7d"], 1)
        self.assertEqual(contas["ativos_30d"], 1)
        self.assertEqual(contas["nunca_acessaram"], 1)

    def test_serie_cobre_todos_os_dias_da_janela(self):
        """A série tem um ponto por dia, inclusive nos dias sem cadastro."""
        self._criar("joana", email="joana@exemplo.com")

        serie = coletar_metricas(dias_serie=7)["cadastros_por_dia"]

        self.assertEqual(len(serie), 7)
        self.assertEqual(serie[-1]["data"], timezone.localdate().isoformat())
        self.assertEqual(serie[-1]["total"], 1)
        self.assertTrue(all(ponto["total"] == 0 for ponto in serie[:-1]))

    def test_serie_esta_em_ordem_crescente(self):
        """O gráfico depende da ordem cronológica dos pontos."""
        serie = coletar_metricas(dias_serie=5)["cadastros_por_dia"]

        datas = [ponto["data"] for ponto in serie]
        self.assertEqual(datas, sorted(datas))

    def test_nao_expoe_dado_financeiro(self):
        """O painel administrativo não devolve valor, saldo nem ativo.

        Espelha a mesma fronteira verificada nos testes de endpoint: administrar a
        plataforma não exige ver as finanças de ninguém.
        """
        self._criar("joana", email="joana@exemplo.com")

        conteudo = str(coletar_metricas()).lower()

        for termo in ("valor", "saldo", "patrimonio", "receita", "despesa"):
            self.assertNotIn(termo, conteudo)
