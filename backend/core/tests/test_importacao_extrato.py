import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from core.models import CartaoCredito, ExtratoImportado, LinhaExtrato, Conta
from core.services.extrato_parser import processar_pdf

class ImportacaoExtratoTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.cartao = CartaoCredito.objects.create(
            usuario=self.user,
            nome="Santander Teste",
            bandeira="VISA",
            ultimos_digitos="6393",
            limite=Decimal("5000.00"),
            dia_fechamento=15,  # Fechamento dia 15
            dia_vencimento=25,   # Vencimento dia 25
            ativo=True
        )
        self.pdf_path = "/app/docs/Faturas/Fatura Maio.pdf"

    @unittest.skipIf(not os.path.exists("/app/docs/Faturas/Fatura Maio.pdf"), "Real test PDF not present in environment")
    def test_santander_parser_directly(self):
        """Valida que o parser do Santander extrai corretamente as transações do PDF real."""
        self.assertTrue(os.path.exists(self.pdf_path), f"Fatura de teste não encontrada em {self.pdf_path}")
        
        linhas = processar_pdf(self.pdf_path, banco="santander")
        
        self.assertGreater(len(linhas), 0)
        
        # Verifica se algumas transações conhecidas da fatura estão presentes
        descricoes = [l["descricao"] for l in linhas]
        
        # Kabum-Kabum e Spotify devem estar lá
        self.assertTrue(any("KABUM-KABUM" in desc for desc in descricoes))
        self.assertTrue(any("SPOTIFY" in desc for desc in descricoes))
        
        # Verifica estrutura dos dados extraídos
        for l in linhas:
            self.assertIn("data", l)
            self.assertIn("descricao", l)
            self.assertIn("valor", l)
            self.assertIn("tipo", l)
            self.assertIsInstance(l["data"], date)
            self.assertIsInstance(l["valor"], Decimal)
            self.assertEqual(l["tipo"], "D")  # Todos devem ser despesas/débitos

    @patch('core.services.fatura_service.detectar_vencimento_fatura')
    @patch('core.services.extrato_parser.processar_pdf')
    def test_upload_extrato_endpoint(self, mock_processar, mock_detectar):
        """Testa o endpoint de upload POST /api/ferramentas/importar-extrato/"""
        # mock parser lines
        mock_processar.return_value = [
            {"data": date(2026, 5, 10), "descricao": "SPOTIFY", "valor": Decimal("20.90"), "tipo": "D"},
            {"data": date(2026, 5, 12), "descricao": "KABUM-KABUM", "valor": Decimal("150.00"), "tipo": "D"}
        ]
        mock_detectar.return_value = date(2026, 5, 25)

        token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Send a dummy file instead of the real missing PDF
        import io
        dummy_file = io.BytesIO(b"dummy pdf content")
        dummy_file.name = "test_fatura.pdf"

        response = self.client.post(
            "/api/ferramentas/importar-extrato/",
            {
                "arquivo": dummy_file,
                "cartao": str(self.cartao.uuid),
                "banco": "santander"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["linhas_encontradas"], 2)
        self.assertEqual(response.json()["linhas_adicionadas"], 2)

        # Verifica banco de dados - compras criadas diretamente
        contas = Conta.objects.filter(usuario=self.user, eh_fatura_cartao=False)
        self.assertEqual(contas.count(), 2)

    @patch('core.services.extrato_parser.processar_pdf')
    def test_reconciliacao_due_date_calculation(self, mock_processar):
        """Testa se o processamento direto do upload calcula corretamente o vencimento (data_prevista)"""
        # Compra antes do fechamento (Compra: 10/05, Fechamento: 15/05, Vencimento: 25/05)
        # Compra após o fechamento (Compra: 18/05, Fechamento: 15/05, Vencimento: 25/06)
        mock_processar.return_value = [
            {"data": date(2026, 5, 10), "descricao": "Compra Antes Fechamento", "valor": Decimal("100.00"), "tipo": "D"},
            {"data": date(2026, 5, 18), "descricao": "Compra Apos Fechamento", "valor": Decimal("50.00"), "tipo": "D"}
        ]

        token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        import io
        dummy_file = io.BytesIO(b"dummy pdf content")
        dummy_file.name = "test_fatura.pdf"

        response = self.client.post(
            "/api/ferramentas/importar-extrato/",
            {
                "arquivo": dummy_file,
                "cartao": str(self.cartao.uuid),
                "banco": "santander"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["linhas_adicionadas"], 2)

        # Verificar as compras individuais criadas e suas datas previstas
        contas = Conta.objects.filter(
            usuario=self.user, eh_fatura_cartao=False
        ).order_by("data_compra")
        self.assertEqual(contas.count(), 2)

        conta_antes = contas.filter(descricao="Compra Antes Fechamento").first()
        conta_apos = contas.filter(descricao="Compra Apos Fechamento").first()

        self.assertIsNotNone(conta_antes)
        self.assertIsNotNone(conta_apos)

        # Compra de 10/05 deve vencer no mesmo mês (25/05/2026)
        self.assertEqual(conta_antes.data_prevista, date(2026, 5, 25))
        self.assertEqual(conta_antes.data_compra, date(2026, 5, 10))
        self.assertFalse(conta_antes.transacao_realizada)

        # Compra de 18/05 (pós-fechamento dia 15) deve vencer no mês seguinte (25/06/2026)
        self.assertEqual(conta_apos.data_prevista, date(2026, 6, 25))
        self.assertEqual(conta_apos.data_compra, date(2026, 5, 18))
        self.assertFalse(conta_apos.transacao_realizada)

        # Verificar que as faturas consolidadas foram criadas automaticamente pelo signal
        faturas = Conta.objects.filter(
            usuario=self.user, eh_fatura_cartao=True
        ).order_by("data_prevista")
        self.assertEqual(faturas.count(), 2, "Dois meses diferentes = duas faturas consolidadas")

        fatura_maio = faturas.filter(data_prevista__month=5).first()
        fatura_junho = faturas.filter(data_prevista__month=6).first()

        self.assertIsNotNone(fatura_maio, "Fatura de Maio deve ter sido criada")
        self.assertIsNotNone(fatura_junho, "Fatura de Junho deve ter sido criada")
        self.assertEqual(fatura_maio.valor, Decimal("100.00"))
        self.assertEqual(fatura_junho.valor, Decimal("50.00"))
        self.assertFalse(fatura_maio.transacao_realizada)
        self.assertFalse(fatura_junho.transacao_realizada)

    def test_sync_compra_com_fatura_paga_na_criacao(self):
        """Valida que criar uma compra de cartão vinculada a uma fatura já PAGA a marca como paga automaticamente."""
        # 1. Criar fatura consolidada paga
        data_pagamento = date(2026, 5, 24)
        fatura = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Fatura Paga",
            valor=Decimal("150.00"),
            data_prevista=date(2026, 5, 25),
            cartao=self.cartao,
            eh_fatura_cartao=True,
            transacao_realizada=True,
            data_realizacao=data_pagamento
        )

        # 2. Criar nova compra individual de cartão para o mesmo vencimento
        compra = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Compra Retroativa",
            valor=Decimal("50.00"),
            data_prevista=date(2026, 5, 25),
            cartao=self.cartao,
            eh_fatura_cartao=False
        )

        # 3. Validar se herdou o estado de paga e a data de realização da fatura
        self.assertTrue(compra.transacao_realizada)
        self.assertEqual(compra.data_realizacao, data_pagamento)

    def test_sync_compra_com_fatura_paga_na_edicao(self):
        """Valida que editar o vencimento de uma compra para um mês com fatura paga a marca como paga."""
        # 1. Fatura paga em Maio
        fatura_maio = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Fatura Maio Paga",
            valor=Decimal("100.00"),
            data_prevista=date(2026, 5, 25),
            cartao=self.cartao,
            eh_fatura_cartao=True,
            transacao_realizada=True,
            data_realizacao=date(2026, 5, 24)
        )

        # 2. Compra criada pendente para Junho (fatura não existe)
        compra = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Compra de Junho",
            valor=Decimal("80.00"),
            data_prevista=date(2026, 6, 25),
            cartao=self.cartao,
            eh_fatura_cartao=False
        )
        self.assertFalse(compra.transacao_realizada)

        # 3. Editar vencimento para Maio (fatura paga)
        compra.data_prevista = date(2026, 5, 25)
        compra.save()

        # 4. Validar se a compra foi atualizada para paga automaticamente
        self.assertTrue(compra.transacao_realizada)
        self.assertEqual(compra.data_realizacao, date(2026, 5, 24))

    def test_edit_fatura_cartao_metadata(self):
        """Valida que editar a descrição e categoria de uma fatura de cartão via API funciona, ignorando alterações de valor/vencimento."""
        fatura = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Fatura Original",
            valor=Decimal("100.00"),
            data_prevista=date(2026, 5, 25),
            cartao=self.cartao,
            eh_fatura_cartao=True
        )

        token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Tenta editar tudo (incluindo tentar alterar o valor e a data de vencimento)
        response = self.client.put(
            f"/api/financeiro/contas-pagar/{fatura.id}/",
            {
                "descricao": "Fatura Alterada",
                "categoria": "Cartão/Alimentação",
                "valor": "999.00",  # Tentativa de alteração que deve ser ignorada
                "data_vencimento": "2026-06-25"  # Tentativa de alteração que deve ser ignorada
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fatura.refresh_from_db()
        
        # A descrição deve ter mudado
        self.assertEqual(fatura.descricao, "Fatura Alterada")
        # A categoria deve ter mudado
        self.assertEqual(fatura.categoria.nome, "Cartão/Alimentação")
        # O valor e a data_prevista devem ter sido preservados (não alterados)
        self.assertEqual(fatura.valor, Decimal("100.00"))
        self.assertEqual(fatura.data_prevista, date(2026, 5, 25))

    def test_migration_corrigir_compras_faturas_pagas(self):
        """Valida que a data migration corrige compras individuais que ficaram acumuladas/pendentes em faturas pagas."""
        # 1. Fatura paga
        fatura = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Fatura Paga",
            valor=Decimal("200.00"),
            data_prevista=date(2026, 5, 25),
            cartao=self.cartao,
            eh_fatura_cartao=True,
            transacao_realizada=True,
            data_realizacao=date(2026, 5, 24)
        )

        # 2. Desabilitar temporariamente a sincronização automática no save do model Conta
        # para simular compras órfãs antigas salvas incorretamente como pendentes.
        # Faremos isso simulando salvamento direto no banco ou usando update() que ignora save().
        compra_acumulada = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Compra Pendente Acumulada",
            valor=Decimal("60.00"),
            data_prevista=date(2026, 5, 25),
            cartao=self.cartao,
            eh_fatura_cartao=False
        )
        Conta.objects.filter(pk=compra_acumulada.pk).update(transacao_realizada=False, data_realizacao=None)
        
        compra_acumulada.refresh_from_db()
        self.assertFalse(compra_acumulada.transacao_realizada)

        # 3. Executar a função da data migration diretamente
        import importlib
        from django.apps import apps
        migration_module = importlib.import_module('core.migrations.0002_corrigir_compras_faturas_pagas')
        corrigir_compras_faturas_pagas = migration_module.corrigir_compras_faturas_pagas
        
        corrigir_compras_faturas_pagas(apps, None)

        # 4. Validar se a compra acumulada foi devidamente corrigida para paga
        compra_acumulada.refresh_from_db()
        self.assertTrue(compra_acumulada.transacao_realizada)
        self.assertEqual(compra_acumulada.data_realizacao, date(2026, 5, 24))

    def test_detectar_vencimento_fatura(self):
        """Testa se a detecção heurística do vencimento da fatura escolhe a moda correta."""
        from core.services.fatura_service import detectar_vencimento_fatura
        
        # Simula linhas extraídas de uma fatura de Maio (Fechamento: 15/05, Vencimento: 25/05)
        # Compras normais do mês: vencimento em 25/05/2026
        # Parcela antiga: compra original em 10/04/2026 -> vencimento seria 25/04/2026
        linhas = [
            {"data": date(2026, 5, 10), "tipo": "D"},
            {"data": date(2026, 5, 12), "tipo": "D"},
            {"data": date(2026, 4, 20), "tipo": "D"}, # pós-fechamento de abril (15/04) -> vence 25/05
            {"data": date(2026, 4, 10), "tipo": "D"}, # parcela antiga -> vence 25/04
        ]
        
        vencimento_detectado = detectar_vencimento_fatura(linhas, self.cartao)
        self.assertEqual(vencimento_detectado, date(2026, 5, 25))

    @patch('core.services.extrato_parser.processar_pdf')
    def test_upload_parcela_antiga(self, mock_processar):
        """Valida que uma compra de mês anterior (parcela) é associada ao vencimento da fatura importada atual."""
        # Parcela de compra realizada em 10/04 (vencimento original seria 25/04)
        mock_processar.return_value = [
            {"data": date(2026, 4, 10), "descricao": "Compra Parcelada Antiga 2/3", "valor": Decimal("120.00"), "tipo": "D"},
            # Adiciona mais compras em Maio para definir a moda do vencimento como 25/05
            {"data": date(2026, 5, 10), "descricao": "Outra Compra 1", "valor": Decimal("50.00"), "tipo": "D"},
            {"data": date(2026, 5, 12), "descricao": "Outra Compra 2", "valor": Decimal("30.00"), "tipo": "D"}
        ]

        token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        import io
        dummy_file = io.BytesIO(b"dummy pdf content")
        dummy_file.name = "test_fatura.pdf"

        response = self.client.post(
            "/api/ferramentas/importar-extrato/",
            {
                "arquivo": dummy_file,
                "cartao": str(self.cartao.uuid),
                "banco": "santander"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["linhas_adicionadas"], 3)

        # Verificar se a compra individual criada foi corretamente ajustada
        compra = Conta.objects.filter(
            usuario=self.user, eh_fatura_cartao=False, descricao="Compra Parcelada Antiga 2/3"
        ).first()

        self.assertIsNotNone(compra)
        # Deve ter o vencimento ajustado para a fatura de Maio (25/05/2026)
        self.assertEqual(compra.data_prevista, date(2026, 5, 25))
        # Mas deve preservar a data da compra original (10/04/2026)
        self.assertEqual(compra.data_compra, date(2026, 4, 10))


