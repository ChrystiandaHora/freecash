"""Testes das categorias sugeridas criadas para cada usuário.

O formulário de lançamento sugere as categorias do usuário; sem uma lista inicial,
cada um digitava o nome do seu jeito e os relatórios por categoria se espalhavam.
"""

import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Categoria
from core.services.categoria_service import (
    CATEGORIAS_SUGERIDAS,
    criar_categorias_sugeridas,
)
from core.services.criar_usuario import criar_usuario_com_ecosistema

User = get_user_model()


class CategoriasSugeridasTests(TestCase):
    """Cobre a criação das sugestões no cadastro e a função que as garante."""

    def _novo_usuario(self):
        """Cria um usuário pelo mesmo serviço do cadastro."""
        return criar_usuario_com_ecosistema(
            username="bia", senha="senha-bem-comprida-123", email="bia@exemplo.com",
        )

    def test_cadastro_cria_sugestoes_de_despesa_e_receita_com_o_tipo_certo(self):
        usuario = self._novo_usuario()

        for tipo, nomes in CATEGORIAS_SUGERIDAS.items():
            for nome in nomes:
                categoria = Categoria.objects.get(usuario=usuario, nome=nome)
                self.assertEqual(categoria.tipo, tipo, nome)

    def test_sugestoes_nao_disputam_o_posto_de_categoria_padrao(self):
        usuario = self._novo_usuario()

        padroes_despesa = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA, is_default=True,
        )

        # O lançamento em lote usa a padrão de despesa quando a linha vem sem categoria
        self.assertEqual(list(padroes_despesa.values_list("nome", flat=True)), ["Gastos"])

    def test_cartao_de_credito_nao_e_sugerido(self):
        nomes = [nome for lista in CATEGORIAS_SUGERIDAS.values() for nome in lista]

        self.assertNotIn("Cartão de Crédito", nomes)

    def test_contas_da_casa_ficam_em_moradia(self):
        despesas = CATEGORIAS_SUGERIDAS[Categoria.TIPO_DESPESA]

        self.assertIn("Moradia", despesas)
        self.assertNotIn("Contas da casa", despesas)

    def test_rodar_de_novo_nao_duplica(self):
        usuario = self._novo_usuario()
        total = Categoria.objects.filter(usuario=usuario).count()

        criar_categorias_sugeridas(usuario)

        self.assertEqual(Categoria.objects.filter(usuario=usuario).count(), total)

    def test_preserva_categoria_existente_com_mesmo_nome_e_outro_tipo(self):
        usuario = User.objects.create_user(username="caio", password="senha-bem-comprida-123")
        nome = CATEGORIAS_SUGERIDAS[Categoria.TIPO_DESPESA][0]
        existente = Categoria.objects.create(
            usuario=usuario, nome=nome, tipo=Categoria.TIPO_RECEITA,
        )

        criar_categorias_sugeridas(usuario)

        existente.refresh_from_db()
        self.assertEqual(existente.tipo, Categoria.TIPO_RECEITA)


class MigrationCategoriasSugeridasTests(TestCase):
    """Cobre a migration que cria as sugestões para quem já tinha conta."""

    def _rodar_migration(self):
        """Executa a função da migration contra o registro de apps atual."""
        migration = importlib.import_module("core.migrations.0004_categorias_sugeridas")
        migration.criar_para_usuarios_existentes(django_apps, None)

    def test_cria_o_que_falta_sem_tocar_no_que_o_usuario_ja_tem(self):
        usuario = User.objects.create_user(username="davi", password="senha-bem-comprida-123")
        mercado = Categoria.objects.create(
            usuario=usuario, nome="Mercado", tipo=Categoria.TIPO_RECEITA,
        )
        # A lista da migration é congelada e pode divergir da atual (ex.: "Contas da casa")
        migration = importlib.import_module("core.migrations.0004_categorias_sugeridas")
        esperado = sum(len(nomes) for nomes in migration.CATEGORIAS.values())

        self._rodar_migration()
        self._rodar_migration()

        mercado.refresh_from_db()
        self.assertEqual(mercado.tipo, Categoria.TIPO_RECEITA)
        self.assertEqual(Categoria.objects.filter(usuario=usuario).count(), esperado)
