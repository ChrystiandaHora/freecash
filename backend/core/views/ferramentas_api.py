"""REST API Views para Ferramentas & Ajustes (importação, conciliação, exportação e contas)."""

import os
import re
import tempfile
from datetime import date

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import CartaoCredito, ConfigUsuario, Conta, ExtratoImportado, LinhaExtrato
from core.permissions import EmailVerificadoOuCarencia
from core.serializers import (
    CartaoCreditoSerializer,
    ExtratoImportadoSerializer,
    LinhaExtratoSerializer,
)


def _ja_ocorreu(data_movimento: date) -> bool:
    """Verifica se a linha de extrato já ocorreu (evita marcar agendamento futuro como realizado)."""
    return data_movimento <= timezone.localdate()


class FerramentasImportarAPIView(APIView):
    """Upload de arquivos de backup (.fcbk)."""

    permission_classes = [permissions.IsAuthenticated, EmailVerificadoOuCarencia]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request) -> Response:
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
    """Upload e extração de lançamentos de faturas de cartão de crédito (PDF)."""

    permission_classes = [permissions.IsAuthenticated, EmailVerificadoOuCarencia]
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

            data_vencimento_fatura = detectar_vencimento_fatura(linhas_extraidas, cartao_obj)

            from core.services.fatura_service import obter_categoria_cartao
            categoria_cartao = obter_categoria_cartao(request.user)

            count = 0
            for line in linhas_extraidas:
                tipo_conta = 'R' if line.get('tipo', 'D') == 'C' else 'D'
                transacao_realizada = _ja_ocorreu(line['data'])
                data_prevista = line['data']
                data_compra = None
                categoria = None

                if cartao_obj and tipo_conta == 'D':
                    from core.services.fatura_service import calcular_vencimento_fatura
                    transacao_realizada = False
                    data_compra = line['data']
                    categoria = categoria_cartao
                    data_prevista = calcular_vencimento_fatura(
                        data_compra,
                        cartao_obj.dia_fechamento,
                        cartao_obj.dia_vencimento
                    )
                    if data_vencimento_fatura and data_prevista < data_vencimento_fatura:
                        data_prevista = data_vencimento_fatura

                exists = Conta.objects.filter(
                    usuario=request.user,
                    tipo=tipo_conta,
                    descricao=line['descricao'],
                    valor=line['valor'],
                    cartao=cartao_obj,
                    data_compra=data_compra,
                    data_prevista=data_prevista
                ).exists()

                if not exists:
                    Conta.objects.create(
                        usuario=request.user,
                        tipo=tipo_conta,
                        descricao=line['descricao'],
                        valor=line['valor'],
                        data_prevista=data_prevista,
                        transacao_realizada=transacao_realizada,
                        data_realizacao=line['data'] if transacao_realizada else None,
                        cartao=cartao_obj,
                        data_compra=data_compra,
                        categoria=categoria,
                    )
                    count += 1

            return Response(
                {
                    'ok': True,
                    'msg': f'Fatura processada com sucesso. {len(linhas_extraidas)} lançamentos encontrados, {count} novos adicionados.',
                    'linhas_encontradas': len(linhas_extraidas),
                    'linhas_adicionadas': count
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


class FerramentasConciliacaoUploadAPIView(APIView):
    """Upload de PDF que enfileira linhas para revisão, sem criar lançamento.

    Contrapartida de `FerramentasImportarExtratoAPIView`: aquele cria `Conta` na hora e
    exige cartão; aqui o cartão é opcional e nada nasce na base até o usuário aprovar
    linha a linha. Sem cartão, a linha aprovada vira conta a pagar avulsa.
    Ver docs/importacao-extrato.md.
    """

    permission_classes = [permissions.IsAuthenticated, EmailVerificadoOuCarencia]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request) -> Response:
        arquivo = request.FILES.get('arquivo')
        banco = request.data.get('banco', 'generico')
        cartao_uuid = request.data.get('cartao') or None

        if not arquivo:
            return Response(
                {'erro': 'Nenhum arquivo enviado. Use o campo "arquivo".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        bancos_validos = {escolha[0] for escolha in ExtratoImportado.BANCO_CHOICES}
        if banco not in bancos_validos:
            return Response(
                {'erro': f'Banco inválido. Use um de: {", ".join(sorted(bancos_validos))}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cartao_obj = None
        if cartao_uuid:
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
            linhas_extraidas = processar_pdf(temp_path, banco=banco)

            if not linhas_extraidas:
                return Response(
                    {'erro': 'Nenhuma transação encontrada no arquivo ou formato incompatível.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            data_vencimento = None
            if cartao_obj:
                from core.services.fatura_service import detectar_vencimento_fatura
                data_vencimento = detectar_vencimento_fatura(linhas_extraidas, cartao_obj)

            extrato = ExtratoImportado.objects.create(
                usuario=request.user,
                arquivo_nome=arquivo.name[:255],
                banco=banco,
                status='processado',
                linhas_encontradas=len(linhas_extraidas),
                cartao=cartao_obj,
                data_vencimento=data_vencimento,
            )

            LinhaExtrato.objects.bulk_create([
                LinhaExtrato(
                    extrato=extrato,
                    data=linha['data'],
                    descricao=linha['descricao'][:500],
                    valor=linha['valor'],
                    tipo=linha.get('tipo', 'D'),
                )
                for linha in linhas_extraidas
            ])

            return Response(
                ExtratoImportadoSerializer(extrato).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'erro': f'Falha ao processar arquivo: {str(e)}'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class FerramentasConciliacaoListAPIView(APIView):
    """Lista os últimos extratos importados e suas linhas pendentes de conciliação."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
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


class FerramentasConciliacaoLinhaAPIView(APIView):
    """Corrige a natureza (débito/crédito) de uma linha antes da aprovação.

    Existe por causa de um limite real do parser genérico: ele decide o tipo pelo sinal
    de menos (`_extrair_linha`), e extrato que imprime despesa sem sinal sai inteiro como
    crédito — viraria receita e inflaria o saldo. A fila é justamente o lugar de corrigir
    o que a heurística errou, então o conserto é do usuário, e não de um palpite melhor.
    Ver docs/importacao-extrato.md.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request, pk) -> Response:
        tipo = request.data.get('tipo')

        if tipo not in (LinhaExtrato.TIPO_CREDITO, LinhaExtrato.TIPO_DEBITO):
            return Response(
                {'erro': 'Campo "tipo" deve ser "C" ou "D".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            linha = LinhaExtrato.objects.get(
                pk=pk, extrato__usuario=request.user, status='pendente'
            )
        except LinhaExtrato.DoesNotExist:
            return Response(
                {'erro': 'Linha não encontrada ou já revisada.'},
                status=status.HTTP_404_NOT_FOUND
            )

        linha.tipo = tipo
        linha.save(update_fields=['tipo'])

        return Response(LinhaExtratoSerializer(linha).data, status=status.HTTP_200_OK)


class FerramentasConciliacaoProcessarAPIView(APIView):
    """Aprova ou ignora em lote linhas de extrato pendentes."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request) -> Response:
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
        duplicadas = 0
        if acao == 'importar':
            for linha_id in linha_ids:
                try:
                    linha = LinhaExtrato.objects.get(
                        pk=linha_id, extrato=extrato, status='pendente'
                    )
                    tipo_conta = 'R' if linha.tipo == 'C' else 'D'
                    transacao_realizada = _ja_ocorreu(linha.data)
                    data_prevista = linha.data
                    data_compra = None
                    categoria = None

                    if extrato.cartao and tipo_conta == 'D':
                        from core.services.fatura_service import (
                            calcular_vencimento_fatura,
                            obter_categoria_cartao,
                        )
                        transacao_realizada = False
                        data_compra = linha.data
                        categoria = obter_categoria_cartao(request.user)
                        data_prevista = calcular_vencimento_fatura(
                            data_compra,
                            extrato.cartao.dia_fechamento,
                            extrato.cartao.dia_vencimento
                        )
                        if extrato.data_vencimento and data_prevista < extrato.data_vencimento:
                            data_prevista = extrato.data_vencimento

                    # Reimportar o mesmo PDF é o caso comum: vincula ao lançamento que já existe
                    # em vez de duplicar (mesma comparação de campos do caminho direto)
                    duplicada = Conta.objects.filter(
                        usuario=request.user,
                        tipo=tipo_conta,
                        descricao=linha.descricao,
                        valor=linha.valor,
                        cartao=extrato.cartao,
                        data_compra=data_compra,
                        data_prevista=data_prevista,
                    ).first()

                    if duplicada:
                        linha.status = 'importado'
                        linha.conta_vinculada = duplicada
                        linha.save()
                        duplicadas += 1
                        continue

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
                        categoria=categoria,
                    )
                    linha.status = 'importado'
                    linha.conta_vinculada = conta
                    linha.save()
                    count += 1
                except LinhaExtrato.DoesNotExist:
                    continue

            extrato.linhas_importadas += count + duplicadas
            extrato.save(update_fields=['linhas_importadas'])
            return Response(
                {'ok': True, 'importadas': count, 'duplicadas': duplicadas},
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


class FerramentasExportarAPIView(APIView):
    """Exportação de relatórios (xlsx, csv, pdf) e backups (.fcbk)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> HttpResponse:
        formato = request.query_params.get('formato', 'excel')
        escopo = request.query_params.get('escopo', 'completo')
        if escopo not in ('geral', 'investimentos', 'completo'):
            escopo = 'completo'
        usuario = request.user
        apelido = re.sub(r'[^A-Za-z0-9._-]+', '-', usuario.username or 'usuario').strip('-')
        emitido = timezone.localtime().strftime('%Y-%m-%d_%H%M')

        data_inicio_str = request.query_params.get('data_inicio')
        data_fim_str = request.query_params.get('data_fim')

        from datetime import datetime
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
            filename = f'backup_freecash_{apelido}_{emitido}.fcbk'
            response = HttpResponse(payload, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            config, _ = ConfigUsuario.objects.get_or_create(usuario=usuario)
            config.ultimo_export_em = timezone.now()
            config.save(update_fields=['ultimo_export_em'])
            return response

        elif formato == 'excel':
            from core.services.export_report_service import gerar_excel
            payload = gerar_excel(usuario, data_inicio, data_fim, escopo)
            filename = f'relatorio_financeiro_{apelido}_{emitido}.xlsx'
            response = HttpResponse(payload, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        elif formato == 'pdf':
            from core.services.export_report_service import gerar_pdf
            payload = gerar_pdf(usuario, data_inicio, data_fim, escopo)
            filename = f'relatorio_financeiro_{apelido}_{emitido}.pdf'
            response = HttpResponse(payload, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        elif formato == 'csv':
            from core.services.export_report_service import gerar_csv
            payload = gerar_csv(usuario, data_inicio, data_fim, escopo)
            filename = f'relatorio_financeiro_{apelido}_{emitido}.csv'
            response = HttpResponse(payload, content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        else:
            return Response(
                {'erro': f'Formato "{formato}" descontinuado ou inválido. Use "excel", "csv", "pdf" ou "fcbk".'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ContasBancariasViewSet(viewsets.ModelViewSet):
    """CRUD de contas bancárias e cartões de crédito do usuário."""

    serializer_class = CartaoCreditoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartaoCredito.objects.filter(usuario=self.request.user).order_by('nome')

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle_ativo(self, request, pk=None) -> Response:
        """Inverte o status ativo/inativo da conta ou cartão."""
        conta = self.get_object()
        conta.ativo = not conta.ativo
        conta.save(update_fields=['ativo'])
        return Response(
            {'ok': True, 'ativo': conta.ativo},
            status=status.HTTP_200_OK
        )

