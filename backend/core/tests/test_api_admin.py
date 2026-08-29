"""Testes do painel administrativo.

Três propriedades sustentam estes testes:

**Autorização real, não cosmética.** O gate do frontend é conveniência; a recusa
tem de vir do servidor. Um usuário comum precisa receber 403 em toda rota do
painel, e um administrador suspenso deixa de ser administrador na hora.

**A fronteira de privacidade.** O painel expõe metadados de conta e contagens,
nunca valores financeiros. O teste `test_resposta_nao_expoe_dado_financeiro` existe
para falhar caso alguém publique um campo de valor por descuido — é a única
proteção automática dessa fronteira.

**A suspensão encerra a sessão.** Marcar `is_active=False` sem revogar os tokens
deixaria o suspenso operando por até sete dias via refresh token.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Conta, ConfigUsuario, LogAcaoAdmin

User = get_user_model()


class AdminBaseTestCase(APITestCase):
    """Base com um administrador e uma conta comum."""

    def setUp(self):
        """Cria o administrador, um usuário comum e um lançamento do comum."""
        self.admin = User.objects.create_user(
            username="admin", password="senha-bem-comprida-123",
            email="admin@exemplo.com", is_staff=True,
        )
        ConfigUsuario.objects.get_or_create(usuario=self.admin)

        self.comum = User.objects.create_user(
            username="joana", password="senha-bem-comprida-123",
            email="joana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.comum)

        Conta.objects.create(
            usuario=self.comum,
            tipo=Conta.TIPO_DESPESA,
            descricao="Aluguel secreto da Joana",
            valor="4321.99",
            data_prevista=timezone.localdate(),
        )

    def autenticar(self, usuario):
        """Autentica com uma instância recém-carregada do usuário.

        Args:
            usuario (User): Conta a autenticar.
        """
        self.client.force_authenticate(user=User.objects.get(pk=usuario.pk))


class AdminAutorizacaoTests(AdminBaseTestCase):
    """Verifica quem pode alcançar o painel."""

    def rotas_do_painel(self):
        """Enumera as rotas do painel para verificação em bloco.

        Returns:
            list[tuple[str, str]]: Pares de método HTTP e URL.
        """
        return [
            ("get", reverse("api-admin-usuarios")),
            ("get", reverse("api-admin-usuario-detalhe", args=[self.comum.pk])),
            ("get", reverse("api-admin-metricas")),
            ("get", reverse("api-admin-logs")),
            ("post", reverse("api-admin-usuario-suspender", args=[self.comum.pk])),
            ("post", reverse("api-admin-usuario-reativar", args=[self.comum.pk])),
        ]

    def test_usuario_comum_recebe_403_em_todas_as_rotas(self):
        """Sem `is_staff`, o painel inteiro é inacessível."""
        self.autenticar(self.comum)
        for metodo, url in self.rotas_do_painel():
            with self.subTest(url=url):
                resposta = getattr(self.client, metodo)(url)
                self.assertEqual(
                    resposta.status_code,
                    status.HTTP_403_FORBIDDEN,
                    f"{metodo.upper()} {url} devolveu {resposta.status_code}",
                )

    def test_anonimo_recebe_401_em_todas_as_rotas(self):
        """Sem sessão, o painel também é inacessível."""
        for metodo, url in self.rotas_do_painel():
            with self.subTest(url=url):
                resposta = getattr(self.client, metodo)(url)
                self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_administrador_suspenso_perde_o_acesso(self):
        """Suspender um administrador tira o papel dele imediatamente.

        O papel é lido do banco a cada requisição justamente para isto: numa claim
        de JWT, com rotação de refresh token, o valor sobreviveria por sete dias.
        """
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        self.autenticar(self.admin)

        resposta = self.client.get(reverse("api-admin-usuarios"))
        self.assertIn(
            resposta.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_administrador_acessa_o_painel(self):
        """O caminho felizes: administrador ativo enxerga a listagem."""
        self.autenticar(self.admin)
        resposta = self.client.get(reverse("api-admin-usuarios"))
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)


class AdminListagemTests(AdminBaseTestCase):
    """Verifica a listagem, os filtros e a fronteira de privacidade."""

    def setUp(self):
        """Autentica como administrador."""
        super().setUp()
        self.autenticar(self.admin)
        self.url = reverse("api-admin-usuarios")

    def test_listagem_vem_paginada(self):
        """O painel nasce paginado, sem depender do parâmetro `page`."""
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        for chave in ["count", "next", "previous", "results"]:
            self.assertIn(chave, resposta.data)

    def test_resposta_nao_expoe_dado_financeiro(self):
        """A fronteira de privacidade do painel.

        Administrar a plataforma não exige ver as finanças de ninguém. Se este
        teste falhar, um campo de valor foi publicado na API do painel — verifique
        `core/serializers_admin.py` antes de ajustar a expectativa.
        """
        resposta = self.client.get(self.url)
        corpo = str(resposta.data)

        # Nem o valor, nem a descrição do lançamento da Joana podem aparecer.
        self.assertNotIn("4321.99", corpo)
        self.assertNotIn("Aluguel secreto", corpo)

        proibidos = {
            "valor", "saldo", "descricao", "transacoes", "lancamentos",
            "patrimonio", "receita", "despesa",
        }
        for registro in resposta.data["results"]:
            expostos = proibidos.intersection(registro.keys())
            self.assertEqual(
                expostos, set(), f"Campos financeiros expostos: {expostos}"
            )

    def test_listagem_traz_contagem_de_volume(self):
        """Contagem é permitida: dá noção de uso sem revelar conteúdo."""
        resposta = self.client.get(self.url)
        joana = next(
            r for r in resposta.data["results"] if r["username"] == "joana"
        )
        self.assertEqual(joana["total_lancamentos"], 1)
        self.assertEqual(joana["total_ativos"], 0)

    def test_busca_por_email_e_username(self):
        """A busca cobre os dois identificadores."""
        for termo in ["joana", "joana@exemplo.com", "JOANA"]:
            with self.subTest(termo=termo):
                resposta = self.client.get(self.url, {"busca": termo})
                nomes = [r["username"] for r in resposta.data["results"]]
                self.assertEqual(nomes, ["joana"])

    def test_filtro_por_estado_de_verificacao(self):
        """Permite achar quem nunca confirmou o e-mail."""
        config = ConfigUsuario.objects.get(usuario=self.admin)
        config.email_verificado = True
        config.save()

        verificados = self.client.get(self.url, {"verificado": "true"})
        self.assertEqual(
            [r["username"] for r in verificados.data["results"]], ["admin"]
        )

        pendentes = self.client.get(self.url, {"verificado": "false"})
        self.assertEqual(
            [r["username"] for r in pendentes.data["results"]], ["joana"]
        )

    def test_filtro_por_conta_ativa(self):
        """Permite achar as contas suspensas."""
        self.comum.is_active = False
        self.comum.save(update_fields=["is_active"])

        suspensas = self.client.get(self.url, {"ativo": "false"})
        self.assertEqual(
            [r["username"] for r in suspensas.data["results"]], ["joana"]
        )


class AdminSuspensaoTests(AdminBaseTestCase):
    """Verifica a suspensão e a reativação de contas."""

    def setUp(self):
        """Autentica como administrador e resolve as URLs de ação."""
        super().setUp()
        self.autenticar(self.admin)
        self.url_suspender = reverse(
            "api-admin-usuario-suspender", args=[self.comum.pk]
        )
        self.url_reativar = reverse(
            "api-admin-usuario-reativar", args=[self.comum.pk]
        )

    def test_suspensao_desativa_a_conta_e_registra_o_log(self):
        """A ação altera o estado e deixa rastro de quem a executou."""
        resposta = self.client.post(
            self.url_suspender, {"detalhe": "Uso abusivo da importação"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.comum.refresh_from_db()
        self.assertFalse(self.comum.is_active)

        log = LogAcaoAdmin.objects.get()
        self.assertEqual(log.acao, LogAcaoAdmin.ACAO_SUSPENDER)
        self.assertEqual(log.ator_username, "admin")
        self.assertEqual(log.alvo_username, "joana")
        self.assertEqual(log.detalhe, "Uso abusivo da importação")

    def test_suspensao_revoga_as_sessoes_abertas(self):
        """Sem revogar, o suspenso continuaria renovando o acesso por sete dias."""
        refresh = str(RefreshToken.for_user(self.comum))

        self.client.post(self.url_suspender)

        # Cliente separado: o do teste está autenticado como administrador.
        resposta = self.client.post(
            reverse("token_refresh"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_conta_suspensa_nao_consegue_mais_autenticar(self):
        """O login do suspenso é recusado pelo backend de autenticação."""
        self.client.post(self.url_suspender)

        self.client.force_authenticate(user=None)
        resposta = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "joana@exemplo.com", "password": "senha-bem-comprida-123"},
            format="json",
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reativacao_devolve_o_acesso(self):
        """A ação inversa restaura o estado e registra o próprio log."""
        self.client.post(self.url_suspender)
        resposta = self.client.post(self.url_reativar)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.comum.refresh_from_db()
        self.assertTrue(self.comum.is_active)
        self.assertEqual(
            LogAcaoAdmin.objects.filter(acao=LogAcaoAdmin.ACAO_REATIVAR).count(), 1
        )

    def test_administrador_nao_pode_suspender_a_si_mesmo(self):
        """Evita que a plataforma fique sem nenhum administrador operante."""
        url = reverse("api-admin-usuario-suspender", args=[self.admin.pk])
        resposta = self.client.post(url)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(LogAcaoAdmin.objects.count(), 0)

    def test_acao_repetida_e_idempotente_e_nao_duplica_log(self):
        """Suspender duas vezes não gera dois registros da mesma decisão."""
        self.client.post(self.url_suspender)
        segunda = self.client.post(self.url_suspender)

        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(LogAcaoAdmin.objects.count(), 1)

    def test_conta_inexistente_responde_404(self):
        """Alvo inexistente é 404, não erro do servidor."""
        url = reverse("api-admin-usuario-suspender", args=[999999])
        resposta = self.client.post(url)
        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)


class AdminMetricasTests(AdminBaseTestCase):
    """Verifica os indicadores de plataforma."""

    def setUp(self):
        """Autentica como administrador."""
        super().setUp()
        self.autenticar(self.admin)
        self.url = reverse("api-admin-metricas")

    def test_metricas_contam_as_contas(self):
        """Os agregados refletem o estado da base."""
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

        contas = resposta.data["contas"]
        self.assertEqual(contas["total"], 2)
        self.assertEqual(contas["ativas"], 2)
        self.assertEqual(contas["suspensas"], 0)
        self.assertEqual(contas["administradores"], 1)
        self.assertEqual(contas["com_email"], 2)
        self.assertEqual(contas["verificadas"], 0)
        self.assertEqual(contas["nunca_acessaram"], 2)

    def test_percentual_verificado_e_calculado_no_servidor(self):
        """Um único arredondamento, para todos os consumidores."""
        config = ConfigUsuario.objects.get(usuario=self.comum)
        config.email_verificado = True
        config.save()

        resposta = self.client.get(self.url)
        self.assertEqual(resposta.data["percentual_verificado"], 50.0)

    def test_serie_de_cadastros_nao_tem_lacunas(self):
        """Dias sem cadastro vêm com zero, não ausentes.

        Uma série com lacunas produziria um gráfico que sugere continuidade onde
        não há dado.
        """
        resposta = self.client.get(self.url, {"dias": 10})
        serie = resposta.data["cadastros_por_dia"]

        self.assertEqual(len(serie), 10)
        self.assertEqual(sum(item["total"] for item in serie), 2)

    def test_janela_da_serie_tem_teto(self):
        """O parâmetro não pode virar vetor para uma consulta enorme."""
        resposta = self.client.get(self.url, {"dias": 99999})
        self.assertEqual(len(resposta.data["cadastros_por_dia"]), 180)

    def test_dias_invalido_cai_no_padrao(self):
        """Entrada malformada não deve produzir erro do servidor."""
        resposta = self.client.get(self.url, {"dias": "muitos"})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data["cadastros_por_dia"]), 30)
