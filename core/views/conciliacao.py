"""
Views para conciliação bancária via upload de PDF.
"""

import os
import tempfile


from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.models import Conta, ExtratoImportado, LinhaExtrato, CartaoCredito
from core.services.extrato_parser import processar_pdf


class ConciliacaoUploadView(LoginRequiredMixin, View):
    """Upload de arquivo PDF de extrato bancário."""

    def get(self, request):
        extratos = ExtratoImportado.objects.filter(usuario=request.user).order_by(
            "-criada_em"
        )[:10]

        return render(
            request,
            "conciliacao_upload.html",
            {
                "extratos": extratos,
                "cartoes": CartaoCredito.objects.filter(usuario=request.user).order_by(
                    "nome"
                ),
            },
        )

    def post(self, request):
        arquivo = request.FILES.get("arquivo")
        banco = request.POST.get("banco", "generico")

        if not arquivo:
            return render(
                request,
                "conciliacao_upload.html",
                {
                    "error": "Selecione um arquivo PDF",
                },
            )

        if not arquivo.name.lower().endswith(".pdf"):
            return render(
                request,
                "conciliacao_upload.html",
                {
                    "error": "O arquivo deve ser um PDF",
                },
            )

        cartao_id = request.POST.get("cartao")
        cartao = None
        if cartao_id:
            cartao = CartaoCredito.objects.filter(
                id=cartao_id, usuario=request.user
            ).first()

        # Criar registro do extrato
        extrato = ExtratoImportado.objects.create(
            usuario=request.user,
            arquivo_nome=arquivo.name,
            banco=banco,
            cartao=cartao,
            status="pendente",
        )

        try:
            # Salvar arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                for chunk in arquivo.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Processar PDF
            linhas = processar_pdf(tmp_path, banco)

            # Remover arquivo temporário
            os.unlink(tmp_path)

            # Criar linhas de extrato
            for linha_data in linhas:
                LinhaExtrato.objects.create(
                    extrato=extrato,
                    data=linha_data["data"],
                    descricao=linha_data["descricao"],
                    valor=linha_data["valor"],
                    tipo=linha_data["tipo"],
                    status="pendente",
                )

            extrato.linhas_encontradas = len(linhas)
            extrato.status = "processado"
            extrato.save()

            return redirect("conciliacao_staging", pk=extrato.pk)

        except Exception as e:
            extrato.status = "erro"
            extrato.erro_mensagem = str(e)
            extrato.save()

            return render(
                request,
                "conciliacao_upload.html",
                {
                    "error": f"Erro ao processar PDF: {e}",
                },
            )


class ConciliacaoStagingView(LoginRequiredMixin, View):
    """Revisão e importação de linhas extraídas."""

    def get(self, request, pk):
        extrato = get_object_or_404(ExtratoImportado, pk=pk, usuario=request.user)
        linhas = extrato.linhas.filter(status="pendente").order_by("-data", "-id")

        return render(
            request,
            "conciliacao_staging.html",
            {
                "extrato": extrato,
                "linhas": linhas,
            },
        )

    def post(self, request, pk):
        extrato = get_object_or_404(ExtratoImportado, pk=pk, usuario=request.user)
        acao = request.POST.get("acao")
        linha_ids = request.POST.getlist("linha_ids")

        if acao == "importar" and linha_ids:
            count = 0
            for linha_id in linha_ids:
                try:
                    linha = LinhaExtrato.objects.get(
                        pk=linha_id, extrato=extrato, status="pendente"
                    )

                    # Criar Conta
                    # Criar Conta
                    tipo_conta = "R" if linha.tipo == "C" else "D"

                    # Se tiver cartão, é despesa de cartão (não realizada/paga ainda)
                    transacao_realizada = True
                    data_prevista = linha.data
                    data_compra = None

                    if extrato.cartao and tipo_conta == "D":
                        transacao_realizada = False
                        data_compra = linha.data
                        # Tentar chutar vencimento aprox (30 dias)
                        from datetime import timedelta

                        data_prevista = linha.data + timedelta(days=30)

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

                    linha.status = "importado"
                    linha.conta_vinculada = conta
                    linha.save()
                    count += 1
                except LinhaExtrato.DoesNotExist:
                    continue

            extrato.linhas_importadas += count
            extrato.save()

        elif acao == "ignorar" and linha_ids:
            LinhaExtrato.objects.filter(
                pk__in=linha_ids, extrato=extrato, status="pendente"
            ).update(status="ignorado")

        return redirect("conciliacao_staging", pk=pk)


class ConciliacaoDeleteView(LoginRequiredMixin, View):
    """Remove um extrato importado."""

    def post(self, request, pk):
        extrato = get_object_or_404(ExtratoImportado, pk=pk, usuario=request.user)
        extrato.delete()
        return redirect("conciliacao")
