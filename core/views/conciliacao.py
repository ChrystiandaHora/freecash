"""
Views para conciliação bancária via upload de PDF.
"""

import os
import tempfile


from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.models import Conta, ExtratoImportado, LinhaExtrato
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

        # Criar registro do extrato
        extrato = ExtratoImportado.objects.create(
            usuario=request.user,
            arquivo_nome=arquivo.name,
            banco=banco,
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
                    tipo_conta = "R" if linha.tipo == "C" else "D"
                    conta = Conta.objects.create(
                        usuario=request.user,
                        tipo=tipo_conta,
                        descricao=linha.descricao,
                        valor=linha.valor,
                        data_prevista=linha.data,
                        transacao_realizada=True,
                        data_realizacao=linha.data,
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
