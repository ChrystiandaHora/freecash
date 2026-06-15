"""
REST API Views para Bloco B — Ferramentas & Ajustes.

Endpoints expostos:
  POST   /api/ferramentas/importar/                 — upload de extrato (.xlsx, .csv, .fcbk)
  GET    /api/ferramentas/conciliacao/               — lista extratos + linhas pendentes
  POST   /api/ferramentas/conciliacao/processar/     — importa / ignora linhas selecionadas
  GET    /api/ferramentas/exportar/                  — download backup criptografado (.fcbk)
  GET    /api/ferramentas/exportar/csv/              — download CSV das movimentações
  CRUD   /api/configuracoes/contas-bancarias/        — gestão de cartões/contas (CartaoCredito)
"""

import csv
import io
import tempfile
import os

from django.utils import timezone
from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Conta, CartaoCredito, ExtratoImportado, LinhaExtrato, ConfigUsuario
from core.serializers import (
    CartaoCreditoSerializer,
    ContaSerializer,
    ExtratoImportadoSerializer,
    LinhaExtratoSerializer,
)


# ─────────────────────────────────────────────────────────────
# 2.1  IMPORTAR — POST /api/ferramentas/importar/
# ─────────────────────────────────────────────────────────────

class FerramentasImportarAPIView(APIView):
    """View para upload de arquivo e importação de movimentações financeiras.

    Recebe um arquivo (.xlsx / .csv / .fcbk) via multipart/form-data
    e executa o processador universal de importação associado ao usuário.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request) -> Response:
        """Processa a requisição POST realizando o parse e gravação do arquivo importado.

        Args:
            request (Request): Requisição multipart contendo a chave 'arquivo' e opcional 'password'.

        Returns:
            Response: Dicionário contendo estatísticas de registros criados, atualizados ou ignorados.
        """
        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            return Response(
                {'erro': 'Nenhum arquivo enviado. Use o campo "arquivo".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        nome = (arquivo.name or '').lower()
        if not nome.endswith('.fcbk'):
            return Response(
                {'erro': 'Formato inválido. Envie apenas arquivos de backup no formato próprio ".fcbk".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        password = request.data.get('password', None)
        try:
            from core.services.import_service import importar_universal
            resultado = importar_universal(arquivo, request.user, password=password)
            return Response(
                {
                    'ok': True,
                    'msg': resultado.get('msg', 'Importação concluída com sucesso!'),
                    'criados': resultado.get('criados', 0),
                    'atualizados': resultado.get('atualizados', 0),
                    'ignorados': resultado.get('ignorados', 0),
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'erro': f'Falha na importação: {str(e)}'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )


class FerramentasImportarExtratoAPIView(APIView):
    """View para upload de faturas de cartão de crédito (PDF).

    Recebe o arquivo PDF, o UUID do cartão e o banco, executa o parser e salva as linhas de extrato pendentes.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request) -> Response:
        arquivo = request.FILES.get('arquivo')
        cartao_uuid = request.data.get('cartao')
        banco = request.data.get('banco', 'generico')

        if not arquivo:
            return Response(
                {'erro': 'Nenhum arquivo enviado. Use o campo "arquivo".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not cartao_uuid:
            return Response(
                {'erro': 'Cartão de crédito não especificado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cartao_obj = CartaoCredito.objects.get(uuid=cartao_uuid, usuario=request.user)
        except (CartaoCredito.DoesNotExist, ValueError):
            return Response(
                {'erro': 'Cartão de crédito não encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

        suffix = os.path.splitext(arquivo.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in arquivo.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        try:
            from core.services.extrato_parser import processar_pdf
            from core.services.fatura_service import detectar_vencimento_fatura
            linhas_extraidas = processar_pdf(temp_path, banco=banco)

            if not linhas_extraidas:
                return Response(
                    {'erro': 'Nenhuma transação encontrada no arquivo ou formato incompatível.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Detectar data de vencimento da fatura
            data_vencimento_fatura = detectar_vencimento_fatura(linhas_extraidas, cartao_obj)

            # Criar ExtratoImportado
            extrato = ExtratoImportado.objects.create(
                usuario=request.user,
                arquivo_nome=arquivo.name,
                banco=banco,
                status='pendente',
                linhas_encontradas=len(linhas_extraidas),
                linhas_importadas=0,
                cartao=cartao_obj,
                data_vencimento=data_vencimento_fatura
            )

            # Criar LinhaExtrato
            linhas_objs = []
            for line in linhas_extraidas:
                linhas_objs.append(
                    LinhaExtrato(
                        extrato=extrato,
                        data=line['data'],
                        descricao=line['descricao'],
                        valor=line['valor'],
                        tipo=line.get('tipo', 'D'),
                        status='pendente'
                    )
                )
            
            LinhaExtrato.objects.bulk_create(linhas_objs)

            return Response(
                {
                    'ok': True,
                    'msg': f'Fatura importada com sucesso. {len(linhas_extraidas)} lançamentos encontrados.',
                    'linhas_encontradas': len(linhas_extraidas),
                    'extrato_id': extrato.id
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'erro': f'Falha ao processar fatura: {str(e)}'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ─────────────────────────────────────────────────────────────
# 2.2  CONCILIAÇÃO — GET + POST /api/ferramentas/conciliacao/
# ─────────────────────────────────────────────────────────────

class FerramentasConciliacaoListAPIView(APIView):
    """Endpoint responsável por listar os últimos extratos importados do usuário.

    Facilita a visualização rápida e acompanhamento do número de linhas pendentes
    de conciliação no sistema.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Retorna a lista dos 20 extratos importados mais recentes e suas linhas pendentes.

        Args:
            request (Request): Requisição HTTP.

        Returns:
            Response: Payload JSON contendo extratos aninhados com suas linhas de status 'pendente'.
        """
        extratos = ExtratoImportado.objects.filter(
            usuario=request.user
        ).prefetch_related('linhas').order_by('-criada_em')[:20]

        data = []
        for extrato in extratos:
            linhas_pendentes = extrato.linhas.filter(status='pendente').order_by('-data', '-id')
            extrato_data = ExtratoImportadoSerializer(extrato).data
            extrato_data['linhas'] = LinhaExtratoSerializer(linhas_pendentes, many=True).data
            data.append(extrato_data)

        return Response({'extratos': data}, status=status.HTTP_200_OK)


class FerramentasConciliacaoProcessarAPIView(APIView):
    """View para processar a conciliação manual/assistida de linhas de extratos importadas.

    Permite a aprovação e conversão de linhas de extrato brutas em Contas reais,
    ou a marcação das linhas para serem sumariamente ignoradas.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request) -> Response:
        """Processa a importação ou rejeição em lote de linhas de extrato selecionadas.

        Args:
            request (Request): JSON contendo 'acao' ("importar"/"ignorar"), 'extrato_id' e 'linha_ids'.

        Returns:
            Response: Confirmação do número de linhas alteradas com sucesso.
        """
        acao = request.data.get('acao')
        extrato_id = request.data.get('extrato_id')
        linha_ids = request.data.get('linha_ids', [])

        if acao not in ('importar', 'ignorar'):
            return Response(
                {'erro': 'Campo "acao" deve ser "importar" ou "ignorar".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            extrato = ExtratoImportado.objects.get(pk=extrato_id, usuario=request.user)
        except ExtratoImportado.DoesNotExist:
            return Response(
                {'erro': 'Extrato não encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not linha_ids:
            return Response(
                {'erro': 'Nenhuma linha selecionada.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        count = 0
        if acao == 'importar':
            for linha_id in linha_ids:
                try:
                    linha = LinhaExtrato.objects.get(
                        pk=linha_id, extrato=extrato, status='pendente'
                    )
                    tipo_conta = 'R' if linha.tipo == 'C' else 'D'
                    transacao_realizada = True
                    data_prevista = linha.data
                    data_compra = None

                    if extrato.cartao and tipo_conta == 'D':
                        from core.services.fatura_service import calcular_vencimento_fatura
                        transacao_realizada = False
                        data_compra = linha.data
                        data_prevista = calcular_vencimento_fatura(
                            data_compra,
                            extrato.cartao.dia_fechamento,
                            extrato.cartao.dia_vencimento
                        )
                        # Ajustar data_prevista para a data da fatura atual caso seja uma parcela antiga
                        if extrato.data_vencimento and data_prevista < extrato.data_vencimento:
                            data_prevista = extrato.data_vencimento

                    conta = Conta.objects.create(
                        usuario=request.user,
                        tipo=tipo_conta,
                        descricao=linha.descricao,
                        valor=linha.valor,
                        data_prevista=data_prevista,
                        transacao_realizada=transacao_realizada,
                        data_realizacao=linha.data if transacao_realizada else None,
                        cartao=extrato.cartao,
                        data_compra=data_compra,
                    )
                    linha.status = 'importado'
                    linha.conta_vinculada = conta
                    linha.save()
                    count += 1
                except LinhaExtrato.DoesNotExist:
                    continue

            extrato.linhas_importadas += count
            extrato.save(update_fields=['linhas_importadas'])
            return Response(
                {'ok': True, 'importadas': count},
                status=status.HTTP_200_OK
            )

        elif acao == 'ignorar':
            updated = LinhaExtrato.objects.filter(
                pk__in=linha_ids, extrato=extrato, status='pendente'
            ).update(status='ignorado')
            return Response(
                {'ok': True, 'ignoradas': updated},
                status=status.HTTP_200_OK
            )


# ─────────────────────────────────────────────────────────────
# 2.3  EXPORTAR (BACKUP) — GET /api/ferramentas/exportar/
# ─────────────────────────────────────────────────────────────

class FerramentasExportarAPIView(APIView):
    """Endpoint responsável pela exportação agregada de relatórios e backups do usuário.

    Suporta formatação de arquivo em planilha (.xlsx), formato simplificado (.csv),
    relatório visual em documento (.pdf) ou backup completo criptografado do sistema (.fcbk).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> HttpResponse:
        """Processa a solicitação de exportação de dados retornando o arquivo gerado para download.

        Query Params suportados:
            formato (str): 'fcbk', 'excel', 'csv' ou 'pdf'. Defaults to 'excel'.
            escopo (str): 'geral', 'investimentos' ou 'completo'. Defaults to 'completo'.
            senha (str, optional): Senha de criptografia obrigatória para o formato '.fcbk'.
            data_inicio (str, optional): Data no formato YYYY-MM-DD para limite inferior do período.
            data_fim (str, optional): Data no formato YYYY-MM-DD para limite superior do período.

        Args:
            request (Request): Requisição GET com parâmetros de query string.

        Returns:
            HttpResponse: Arquivo binário ou de texto configurado com cabeçalho de download attachment.
        """
        formato = request.query_params.get('formato', 'excel')
        escopo = request.query_params.get('escopo', 'completo')
        usuario = request.user
        agora = timezone.localtime().strftime('%Y%m%d_%H%M%S')

        # Parse de datas
        from datetime import datetime, date
        data_inicio_str = request.query_params.get('data_inicio')
        data_fim_str = request.query_params.get('data_fim')

        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                data_inicio = date(2000, 1, 1)
        else:
            data_inicio = date(2000, 1, 1)

        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                data_fim = timezone.localdate()
        else:
            data_fim = timezone.localdate()

        if formato == 'fcbk':
            senha = request.query_params.get('senha', '')
            if not senha:
                return Response(
                    {'erro': 'O parâmetro "senha" é obrigatório para gerar o backup .fcbk.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from core.services.export_service import export_user_data
            payload = export_user_data(usuario, senha)
            filename = f'backup_freecash_{usuario.username}_{agora}.fcbk'
            response = HttpResponse(payload, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
            config.ultimo_export_em = timezone.now()
            config.save(update_fields=['ultimo_export_em'])
            return response

        elif formato == 'excel':
            from core.services.export_report_service import gerar_excel
            payload = gerar_excel(usuario, data_inicio, data_fim, escopo)
            filename = f'relatorio_financeiro_{usuario.username}_{agora}.xlsx'
            response = HttpResponse(payload, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        elif formato == 'pdf':
            from core.services.export_report_service import gerar_pdf
            payload = gerar_pdf(usuario, data_inicio, data_fim, escopo)
            filename = f'relatorio_financeiro_{usuario.username}_{agora}.pdf'
            response = HttpResponse(payload, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        elif formato == 'csv':
            from core.services.export_report_service import get_movimentacoes, get_investimentos
            output = io.StringIO()
            writer = csv.writer(output)

            if escopo in ('geral', 'completo'):
                if escopo == 'completo':
                    writer.writerow(['--- MOVIMENTACOES GERAIS ---'])
                writer.writerow(['Data', 'Tipo', 'Descricao', 'Categoria', 'Valor (R$)', 'Status'])
                contas = get_movimentacoes(usuario, data_inicio, data_fim)
                for c in contas:
                    writer.writerow([
                        c.data_prevista.strftime('%d/%m/%Y'),
                        c.get_tipo_display(),
                        c.descricao,
                        c.categoria.nome if c.categoria else 'Sem cat.',
                        str(c.valor),
                        'Realizada' if c.transacao_realizada else 'Pendente',
                    ])

            if escopo == 'completo':
                writer.writerow([])
                writer.writerow([])

            if escopo in ('investimentos', 'completo'):
                if escopo == 'completo':
                    writer.writerow(['--- CARTEIRA DE INVESTIMENTOS ---'])
                writer.writerow(['Ticker', 'Nome', 'Classe', 'Categoria', 'Quantidade', 'Preco Medio', 'Valor Investido', 'Valor Atual', 'Lucro/Prejuizo'])
                ativos = get_investimentos(usuario, data_inicio, data_fim)
                for a in ativos:
                    writer.writerow([
                        a.ticker,
                        a.nome or '',
                        a.subcategoria.categoria.classe.nome if a.subcategoria else '',
                        a.subcategoria.categoria.nome if a.subcategoria else '',
                        str(a.quantidade),
                        str(a.preco_medio),
                        str(a.valor_investido),
                        str(a.valor_total_atual),
                        str(a.valor_total_atual - a.valor_investido),
                    ])

            filename = f'relatorio_financeiro_{usuario.username}_{agora}.csv'
            response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        else:
            return Response(
                {'erro': f'Formato "{formato}" descontinuado ou inválido. Use "excel", "csv", "pdf" ou "fcbk".'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ─────────────────────────────────────────────────────────────
# 2.4  CONTAS BANCÁRIAS — CRUD /api/configuracoes/contas-bancarias/
#      Reutiliza o model CartaoCredito (representa contas/cartões)
# ─────────────────────────────────────────────────────────────

class ContasBancariasViewSet(viewsets.ModelViewSet):
    """ViewSet REST completo para gestão de Cartões de Crédito e Contas Bancárias do usuário.

    Utiliza o modelo subjacente CartaoCredito para gerenciar limites, estados de
    ativação e dados essenciais.
    """
    serializer_class = CartaoCreditoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Retorna todas as contas/cartões cadastrados do usuário autenticado (ativos e inativos).

        Returns:
            QuerySet: Contas e cartões ordenados por nome.
        """
        # Inclui todos (ativos e inativos) para que o usuário possa reativar
        return CartaoCredito.objects.filter(usuario=self.request.user).order_by('nome')

    def perform_create(self, serializer):
        """Atribui o usuário autenticado da requisição como proprietário ao criar a conta.

        Args:
            serializer (Serializer): Serializador com dados validados da conta.
        """
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle_ativo(self, request, pk=None) -> Response:
        """Inverte o estado de ativação da conta ou cartão selecionado sem deletar.

        Args:
            request (Request): Requisição HTTP.
            pk (str, optional): Identificador único da conta.

        Returns:
            Response: Dicionário contendo o novo estado da flag 'ativo'.
        """
        conta = self.get_object()
        conta.ativo = not conta.ativo
        conta.save(update_fields=['ativo'])
        return Response(
            {'ok': True, 'ativo': conta.ativo},
            status=status.HTTP_200_OK
        )
