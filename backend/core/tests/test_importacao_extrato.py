import os
import unittest
from datetime import date, timedelta
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
        """O upload calcula o vencimento (data_prevista) corretamente."""
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
        """Compra vinculada a fatura já paga nasce marcada como paga."""
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
        """Mover a compra para um mês de fatura paga a marca como paga."""
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
        """Editar descrição e categoria da fatura funciona; valor e vencimento são ignorados."""
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
        """Parcela de mês anterior entra no vencimento da fatura importada."""
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




class DataFuturaNaImportacaoTests(APITestCase):
    """Impede que o importador invente dinheiro que ainda não entrou.

    O extrato descreve o que aconteceu, mas nem toda linha já aconteceu: fatura e
    agendamento trazem parcela e provento datados à frente. Antes da correção o
    importador marcava tudo como realizado usando a data da linha, e o resultado
    era pior que um rótulo errado — o lançamento sumia da projeção, porque a
    âncora leva `data_realizacao <= ontem` e o fluxo de pendentes leva
    `transacao_realizada=False`. Ele não pertencia a nenhum dos dois.
    """

    def setUp(self):
        """Cria o usuário e um extrato sem cartão, onde a regra de data se aplica."""
        self.user = User.objects.create_user(
            username="importador", password="senha-bem-comprida-123"
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )
        self.hoje = timezone.localdate()
        self.extrato = ExtratoImportado.objects.create(
            usuario=self.user, arquivo_nome="extrato.ofx", banco="generico"
        )

    def _linha(self, data_movimento, tipo="C", valor="1000.00"):
        """Cria uma linha pendente de extrato.

        Returns:
            LinhaExtrato: A linha persistida.
        """
        return LinhaExtrato.objects.create(
            extrato=self.extrato, data=data_movimento,
            descricao="Provento", valor=Decimal(valor), tipo=tipo,
        )

    def _importar(self, linha):
        """Dispara a conciliação assistida para uma linha.

        Returns:
            Response: A resposta do endpoint de processamento.
        """
        return self.client.post(
            "/api/ferramentas/conciliacao/processar/",
            {"acao": "importar", "extrato_id": self.extrato.id,
             "linha_ids": [linha.id]},
            format="json",
        )

    def test_linha_futura_nasce_pendente(self):
        """Salário de daqui a uma semana não pode entrar como já recebido."""
        linha = self._linha(self.hoje + timedelta(days=7))

        self.assertEqual(self._importar(linha).status_code, status.HTTP_200_OK)

        conta = Conta.objects.get(usuario=self.user)
        self.assertFalse(conta.transacao_realizada)
        self.assertIsNone(conta.data_realizacao)
        self.assertEqual(conta.data_prevista, self.hoje + timedelta(days=7))

    def test_linha_passada_nasce_liquidada(self):
        """O caso comum não pode regredir: o que já ocorreu segue realizado."""
        linha = self._linha(self.hoje - timedelta(days=3))

        self.assertEqual(self._importar(linha).status_code, status.HTTP_200_OK)

        conta = Conta.objects.get(usuario=self.user)
        self.assertTrue(conta.transacao_realizada)
        self.assertEqual(conta.data_realizacao, self.hoje - timedelta(days=3))

    def test_linha_de_hoje_nasce_liquidada(self):
        """A fronteira é inclusiva: o que caiu hoje já é caixa."""
        linha = self._linha(self.hoje)

        self.assertEqual(self._importar(linha).status_code, status.HTTP_200_OK)

        conta = Conta.objects.get(usuario=self.user)
        self.assertTrue(conta.transacao_realizada)
        self.assertEqual(conta.data_realizacao, self.hoje)

    @patch('core.services.extrato_parser.processar_pdf')
    def test_upload_direto_tambem_respeita_a_data(self, mock_processar):
        """A regra vale nos dois caminhos: upload direto e conciliação assistida.

        São dois blocos de criação separados no mesmo arquivo, e corrigir só um
        deixaria a porta aberta pela outra.

        O upload exige cartão, e despesa de cartão já nascia pendente por conta do
        vencimento da fatura. Quem atravessa a regra de data aqui é o crédito, que
        não entra no ramo do cartão — era por ali que provento agendado virava
        dinheiro recebido.
        """
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão", limite=Decimal("5000.00"),
            dia_fechamento=15, dia_vencimento=25, ativo=True,
        )
        mock_processar.return_value = [
            {"data": self.hoje - timedelta(days=2), "descricao": "Ocorrido",
             "valor": Decimal("500.00"), "tipo": "C"},
            {"data": self.hoje + timedelta(days=10), "descricao": "Agendado",
             "valor": Decimal("900.00"), "tipo": "C"},
        ]

        import io as _io
        arquivo = _io.BytesIO(b"conteudo")
        arquivo.name = "extrato.pdf"
        resposta = self.client.post(
            "/api/ferramentas/importar-extrato/",
            {"arquivo": arquivo, "cartao": str(cartao.uuid), "banco": "generico"},
            format="multipart",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Conta.objects.get(descricao="Ocorrido").transacao_realizada)

        agendado = Conta.objects.get(descricao="Agendado")
        self.assertFalse(agendado.transacao_realizada)
        self.assertIsNone(agendado.data_realizacao)


class ConciliacaoUploadTestCase(APITestCase):
    """Cobre o upload que enfileira linhas para revisão, sem criar lançamento.

    A fila (`ExtratoImportado` + `LinhaExtrato`) existia no banco desde o início, mas
    nenhum endpoint a populava: o único upload criava `Conta` direto e exigia cartão.
    Estes testes fixam as duas propriedades que fazem a fila valer a pena — nada nasce
    na base antes da aprovação, e o cartão é opcional, que é o que permite a linha
    aprovada virar conta a pagar avulsa.
    """

    def setUp(self):
        """Autentica o usuário e prepara um PDF de mentira; o parser é sempre mockado."""
        self.user = User.objects.create_user(
            username="conciliador", password="senha-bem-comprida-123"
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )
        self.hoje = timezone.localdate()

    def _upload(self, **extra):
        """Envia um PDF para a fila de conciliação.

        Returns:
            Response: A resposta do endpoint de upload.
        """
        import io as _io
        arquivo = _io.BytesIO(b"%PDF-1.4 conteudo")
        arquivo.name = "extrato.pdf"
        return self.client.post(
            "/api/ferramentas/conciliacao/upload/",
            {"arquivo": arquivo, "banco": "generico", **extra},
            format="multipart",
        )

    @patch('core.services.extrato_parser.processar_pdf')
    def test_upload_sem_cartao_enfileira_sem_criar_conta(self, mock_processar):
        """O ponto da fila: o PDF vira linha pendente, e nenhuma Conta nasce ainda."""
        mock_processar.return_value = [
            {"data": self.hoje, "descricao": "ALUGUEL", "valor": Decimal("1800.00"), "tipo": "D"},
            {"data": self.hoje, "descricao": "LUZ", "valor": Decimal("210.00"), "tipo": "D"},
        ]

        resposta = self._upload()

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conta.objects.count(), 0)

        extrato = ExtratoImportado.objects.get(usuario=self.user)
        self.assertIsNone(extrato.cartao)
        self.assertEqual(extrato.linhas_encontradas, 2)
        self.assertEqual(extrato.linhas.filter(status="pendente").count(), 2)

    @patch('core.services.extrato_parser.processar_pdf')
    def test_linha_sem_cartao_aprovada_vira_conta_a_pagar(self, mock_processar):
        """Sem cartão a despesa é avulsa: sem vínculo de fatura e sem data_compra."""
        mock_processar.return_value = [
            {"data": self.hoje + timedelta(days=5), "descricao": "ALUGUEL",
             "valor": Decimal("1800.00"), "tipo": "D"},
        ]
        self._upload()
        extrato = ExtratoImportado.objects.get(usuario=self.user)
        linha = extrato.linhas.get()

        resposta = self.client.post(
            "/api/ferramentas/conciliacao/processar/",
            {"acao": "importar", "extrato_id": extrato.id, "linha_ids": [linha.id]},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        conta = Conta.objects.get(usuario=self.user)
        self.assertEqual(conta.tipo, "D")
        self.assertIsNone(conta.cartao)
        self.assertIsNone(conta.data_compra)
        self.assertFalse(conta.transacao_realizada)  # data futura, regra de _ja_ocorreu
        self.assertEqual(conta.data_prevista, self.hoje + timedelta(days=5))

    @patch('core.services.extrato_parser.processar_pdf')
    def test_reimportar_o_mesmo_pdf_nao_duplica(self, mock_processar):
        """Reimportar é o caso comum; a segunda aprovação vincula, não cria."""
        mock_processar.return_value = [
            {"data": self.hoje, "descricao": "ALUGUEL", "valor": Decimal("1800.00"), "tipo": "D"},
        ]

        for _ in range(2):
            self._upload()

        primeiro, segundo = ExtratoImportado.objects.order_by("id")
        for extrato in (primeiro, segundo):
            self.client.post(
                "/api/ferramentas/conciliacao/processar/",
                {"acao": "importar", "extrato_id": extrato.id,
                 "linha_ids": [linha.id for linha in extrato.linhas.all()]},
                format="json",
            )

        self.assertEqual(Conta.objects.count(), 1)
        conta = Conta.objects.get()
        self.assertEqual(
            [linha.conta_vinculada_id for linha in LinhaExtrato.objects.all()],
            [conta.id, conta.id],
        )

    @patch('core.services.extrato_parser.processar_pdf')
    def test_upload_com_cartao_preenche_vencimento_da_fatura(self, mock_processar):
        """Com cartão, o extrato guarda o vencimento detectado para a aprovação usar."""
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão", limite=Decimal("5000.00"),
            dia_fechamento=15, dia_vencimento=25, ativo=True,
        )
        mock_processar.return_value = [
            {"data": date(2026, 3, 10), "descricao": "MERCADO",
             "valor": Decimal("90.00"), "tipo": "D"},
        ]

        resposta = self._upload(cartao=str(cartao.uuid))

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        extrato = ExtratoImportado.objects.get(usuario=self.user)
        self.assertEqual(extrato.cartao, cartao)
        self.assertEqual(extrato.data_vencimento, date(2026, 3, 25))

    @patch('core.services.extrato_parser.processar_pdf')
    def test_pdf_ilegivel_nao_deixa_extrato_orfao(self, mock_processar):
        """Parser que não achou nada devolve 400 e não cria fila vazia para revisar."""
        mock_processar.return_value = []

        resposta = self._upload()

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ExtratoImportado.objects.count(), 0)

    def test_upload_exige_arquivo(self):
        """Sem arquivo o erro é do cliente, não uma exceção do parser."""
        resposta = self.client.post(
            "/api/ferramentas/conciliacao/upload/", {"banco": "generico"}, format="multipart"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core.services.extrato_parser.processar_pdf')
    def test_cartao_de_outro_usuario_nao_e_aceito(self, mock_processar):
        """O cartão vem por UUID do cliente: precisa ser filtrado pelo dono."""
        alheio = User.objects.create_user(username="outro", password="senha-bem-comprida-123")
        cartao = CartaoCredito.objects.create(
            usuario=alheio, nome="Cartão alheio", limite=Decimal("5000.00"),
            dia_fechamento=15, dia_vencimento=25, ativo=True,
        )

        resposta = self._upload(cartao=str(cartao.uuid))

        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ExtratoImportado.objects.count(), 0)


class CorrecaoNaturezaLinhaTestCase(APITestCase):
    """Cobre a correção de débito/crédito na fila, antes da aprovação.

    O parser genérico decide a natureza pelo sinal de menos: extrato que imprime
    despesa sem sinal sai inteiro como crédito, e aprovado assim viraria receita —
    saldo e projeção inflados, que é o mesmo estrago da regra de data. Como a
    heurística não tem como acertar sozinha, quem corrige é o usuário, na fila.
    """

    def setUp(self):
        """Cria um extrato com uma linha classificada como crédito pelo parser."""
        self.user = User.objects.create_user(
            username="corretor", password="senha-bem-comprida-123"
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )
        self.extrato = ExtratoImportado.objects.create(
            usuario=self.user, arquivo_nome="extrato.pdf", banco="generico"
        )
        self.linha = LinhaExtrato.objects.create(
            extrato=self.extrato, data=timezone.localdate(),
            descricao="ALUGUEL", valor=Decimal("1800.00"), tipo="C",
        )

    def _corrigir(self, tipo, linha_id=None):
        """Troca a natureza de uma linha pendente.

        Returns:
            Response: A resposta do endpoint de correção.
        """
        return self.client.patch(
            f"/api/ferramentas/conciliacao/linha/{linha_id or self.linha.id}/",
            {"tipo": tipo}, format="json",
        )

    def test_corrigir_para_debito_faz_a_linha_virar_despesa(self):
        """O ponto do endpoint: crédito chutado vira despesa e é lançado como tal."""
        self.assertEqual(self._corrigir("D").status_code, status.HTTP_200_OK)

        self.client.post(
            "/api/ferramentas/conciliacao/processar/",
            {"acao": "importar", "extrato_id": self.extrato.id,
             "linha_ids": [self.linha.id]},
            format="json",
        )

        self.assertEqual(Conta.objects.get(usuario=self.user).tipo, "D")

    def test_tipo_invalido_e_recusado(self):
        """`tipo` vem do cliente: só 'C' e 'D' podem chegar ao banco."""
        self.assertEqual(self._corrigir("X").status_code, status.HTTP_400_BAD_REQUEST)
        self.linha.refresh_from_db()
        self.assertEqual(self.linha.tipo, "C")

    def test_linha_ja_revisada_nao_muda_mais(self):
        """Depois de virar lançamento, mexer no tipo da linha não corrigiria a Conta."""
        self.linha.status = "importado"
        self.linha.save(update_fields=["status"])

        self.assertEqual(self._corrigir("D").status_code, status.HTTP_404_NOT_FOUND)

    def test_linha_de_outro_usuario_nao_e_alcancavel(self):
        """O id da linha é sequencial e vem do cliente: precisa filtrar pelo dono."""
        alheio = User.objects.create_user(username="outro2", password="senha-bem-comprida-123")
        extrato_alheio = ExtratoImportado.objects.create(
            usuario=alheio, arquivo_nome="alheio.pdf", banco="generico"
        )
        linha_alheia = LinhaExtrato.objects.create(
            extrato=extrato_alheio, data=timezone.localdate(),
            descricao="ALHEIO", valor=Decimal("10.00"), tipo="C",
        )

        resposta = self._corrigir("D", linha_id=linha_alheia.id)

        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)
        linha_alheia.refresh_from_db()
        self.assertEqual(linha_alheia.tipo, "C")
