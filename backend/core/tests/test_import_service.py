"""Testes de integração para o Serviço de Importação de Backup (.fcbk).

Cobre os fluxos críticos de restauração atômica de dados, incluindo:
- Desconexão de signals Django durante importação em lote
- Recálculo correto de preço médio e quantidade após restore
- Resolução de FKs por chave composta (app_label.ModelName)
- Isolamento multi-tenant (padrão do security_standards.md)
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.services.export_service import export_user_data
from core.services.import_service import restore_user_data_fcbk, decrypt_data_fcbk
from investimento.models import (
    ClasseAtivo,
    CategoriaAtivo,
    SubcategoriaAtivo,
    Ativo,
    Transacao,
)


class RestoreUserDataFcbkTests(TestCase):
    """Testes de integração para a função restore_user_data_fcbk.

    Verifica que a restauração de backups produz o estado correto
    de quantidade e preço médio dos ativos de investimento, sem interferência
    de signals disparados durante a importação em lote.

    Observação: o signal `criar_classificacao_padrao` (investimento/signals.py)
    é disparado automaticamente ao criar um novo User via `create_user`, populando
    ClasseAtivo, CategoriaAtivo e SubcategoriaAtivo padrão. O setUp utiliza
    `get_or_create` para obter a estrutura hierárquica já criada pelo signal.
    """

    def setUp(self):
        """Configura usuário e estrutura de ativos de investimento para os testes.

        Usa get_or_create para a hierarquia de ativos, pois o signal
        `criar_classificacao_padrao` já popula as classes padrão ao criar o User.
        """
        self.user = User.objects.create_user(
            username="testuser_import",
            password="senha_segura_123"
        )
        # O signal criar_classificacao_padrao já cria "Renda Variável" → "Ações" → "Ações Brasil"
        # Usamos get_or_create para obter os objetos sem violar unique_together
        self.classe, _ = ClasseAtivo.objects.get_or_create(
            usuario=self.user, nome="Renda Variável"
        )
        self.categoria, _ = CategoriaAtivo.objects.get_or_create(
            usuario=self.user, classe=self.classe, nome="Ações"
        )
        self.subcategoria, _ = SubcategoriaAtivo.objects.get_or_create(
            usuario=self.user, categoria=self.categoria, nome="Ações Brasil"
        )
        self.ativo = Ativo.objects.create(
            usuario=self.user,
            ticker="PETR4",
            nome="Petróleo Brasileiro S.A.",
            subcategoria=self.subcategoria,
        )

    def _create_transacoes(self):
        """Cria 3 transações de compra/venda para simular uma posição histórica.

        Returns:
            tuple: (ativo, [transacao1, transacao2, transacao3])
        """
        t1 = Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            tipo=Transacao.TIPO_COMPRA,
            data="2024-01-10",
            quantidade=100,
            preco_unitario=30.00,
            valor_total=3000.00,
        )
        t2 = Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            tipo=Transacao.TIPO_COMPRA,
            data="2024-03-15",
            quantidade=50,
            preco_unitario=36.00,
            valor_total=1800.00,
        )
        t3 = Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            tipo=Transacao.TIPO_VENDA,
            data="2024-06-20",
            quantidade=30,
            preco_unitario=40.00,
            valor_total=1200.00,
        )
        return self.ativo, [t1, t2, t3]

    def test_sinal_nao_interfere_no_preco_medio_durante_restauracao(self):
        """Verifica que o preço médio e quantidade são calculados corretamente após restore.

        Após exportar e reimportar o backup, os valores de quantidade e preco_medio
        do ativo devem corresponder exatamente ao cálculo de PM fiscal ponderado
        de todas as transações restauradas, sem interferência de signals parciais.

        Posição esperada:
            Compra 1: 100 @ R$30.00 = R$3.000,00
            Compra 2:  50 @ R$36.00 = R$1.800,00
            Total custódia: 150 unidades, custo total = R$4.800,00
            PM = R$4.800 / 150 = R$32.00
            Venda 30 unidades (PM não muda): 150 - 30 = 120 unidades
        """
        self._create_transacoes()

        # Exporta backup criptografado
        senha = "senha_de_teste_segura"
        encrypted = export_user_data(self.user, senha)

        # Decodifica o backup para obter o dict de dados brutos
        data_dict = decrypt_data_fcbk(encrypted.encode(), senha)

        # Garante que o backup contém os dados de investimento
        ativos_no_backup = data_dict.get("data", {}).get("investimento", {}).get("Ativo", [])
        self.assertGreater(len(ativos_no_backup), 0, "O backup não contém ativos de investimento.")

        transacoes_no_backup = data_dict.get("data", {}).get("investimento", {}).get("Transacao", [])
        self.assertEqual(len(transacoes_no_backup), 3, "O backup deve conter 3 transações.")

        # Remove todos os dados do usuário e reimporta via restore
        Transacao.objects.filter(usuario=self.user).delete()
        Ativo.objects.filter(usuario=self.user).delete()
        SubcategoriaAtivo.objects.filter(usuario=self.user).delete()
        CategoriaAtivo.objects.filter(usuario=self.user).delete()
        ClasseAtivo.objects.filter(usuario=self.user).delete()

        resultado = restore_user_data_fcbk(data_dict, self.user)

        # Valida estatísticas do restore
        self.assertGreater(resultado["criados"], 0, "O restore deve criar pelo menos um registro.")

        # Valida estado final do ativo
        ativo_restaurado = Ativo.objects.get(usuario=self.user, ticker="PETR4")

        # Quantidade esperada: 100 + 50 - 30 = 120
        self.assertEqual(
            float(ativo_restaurado.quantidade), 120.0,
            f"Quantidade incorreta após restore: {ativo_restaurado.quantidade}"
        )

        # PM esperado: (100*30 + 50*36) / 150 = 4800/150 = R$32,00
        self.assertAlmostEqual(
            float(ativo_restaurado.preco_medio), 32.0, places=2,
            msg=f"Preço médio incorreto após restore: {ativo_restaurado.preco_medio}"
        )

        # Valida que as 3 transações foram restauradas
        transacoes_restauradas = Transacao.objects.filter(usuario=self.user, ativo=ativo_restaurado)
        self.assertEqual(
            transacoes_restauradas.count(), 3,
            f"Número de transações incorreto após restore: {transacoes_restauradas.count()}"
        )

    def test_restore_preserva_isolamento_multi_tenant(self):
        """Garante que o restore não afeta dados de outros usuários (multi-tenant).

        Cria um segundo usuário com dados independentes e verifica que o restore
        do primeiro usuário não altera os dados do segundo, seguindo o princípio
        de isolamento definido em security_standards.md (seção 2).
        """
        outro_user = User.objects.create_user(
            username="outro_usuario_import",
            password="outra_senha_123"
        )
        # Obtém a estrutura já criada pelo signal para outro_user
        classe2, _ = ClasseAtivo.objects.get_or_create(
            usuario=outro_user, nome="Renda Fixa"
        )
        categoria2, _ = CategoriaAtivo.objects.get_or_create(
            usuario=outro_user, classe=classe2, nome="Pós-fixado (Indexado)"
        )
        subcategoria2, _ = SubcategoriaAtivo.objects.get_or_create(
            usuario=outro_user, categoria=categoria2, nome="CDB/RDB"
        )
        ativo_outro = Ativo.objects.create(
            usuario=outro_user,
            ticker="CDBBCO",
            nome="CDB Banco X",
            subcategoria=subcategoria2,
        )
        Transacao.objects.create(
            usuario=outro_user,
            ativo=ativo_outro,
            tipo=Transacao.TIPO_COMPRA,
            data="2024-01-01",
            quantidade=10,
            preco_unitario=1000.00,
            valor_total=10000.00,
        )

        # Faz backup e restore do usuário principal
        senha = "senha_principal"
        encrypted = export_user_data(self.user, senha)
        data_dict = decrypt_data_fcbk(encrypted.encode(), senha)
        restore_user_data_fcbk(data_dict, self.user)

        # Dados do outro usuário devem permanecer intactos
        self.assertTrue(
            Ativo.objects.filter(usuario=outro_user, ticker="CDBBCO").exists(),
            "O restore do usuário principal apagou dados de outro usuário!"
        )
        transacoes_outro = Transacao.objects.filter(usuario=outro_user)
        self.assertEqual(
            transacoes_outro.count(), 1,
            "O restore afetou o número de transações de outro usuário!"
        )
