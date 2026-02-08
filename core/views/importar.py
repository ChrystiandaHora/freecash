from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate

from core.services.import_service import importar_universal


@method_decorator(login_required, name="dispatch")
class ImportarView(View):
    template_name = "importar.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            messages.error(request, "Selecione um arquivo para importar.")
            return redirect("importar")

        nome = (arquivo.name or "").lower()
        if not (
            nome.endswith(".xlsx") or nome.endswith(".csv") or nome.endswith(".fcbk")
        ):
            messages.error(
                request, "Formato inválido. Envie um arquivo .xlsx, .csv ou .fcbk."
            )
            return redirect("importar")

        password = request.POST.get("password")
        try:
            resultado = importar_universal(arquivo, request.user, password=password)
            messages.success(
                request, resultado.get("msg") or "Importação concluída com sucesso!"
            )
            return redirect("importar")
        except Exception as e:
            messages.error(request, f"Falha na importação: {e}")
            return redirect("importar")


@method_decorator(login_required, name="dispatch")
class ImportarRelatorioView(View):
    """Importa relatório de movimentações a partir de arquivo Excel."""

    template_name = "importar_relatorio.html"

    def get(self, request):
        # Limpa dados de sessão anteriores
        if "importar_relatorio_dados" in request.session:
            del request.session["importar_relatorio_dados"]
        if "importar_relatorio_resumo" in request.session:
            del request.session["importar_relatorio_resumo"]
        return render(request, self.template_name)

    def post(self, request):
        from core.services.import_report_service import (
            ler_excel_relatorio,
            validar_dados_relatorio,
        )

        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return render(
                request, self.template_name, {"error": "Selecione um arquivo."}
            )

        nome = (arquivo.name or "").lower()
        if not nome.endswith(".xlsx"):
            return render(
                request,
                self.template_name,
                {"error": "Formato inválido. Envie um arquivo .xlsx."},
            )

        # Lê o arquivo Excel
        resultado = ler_excel_relatorio(arquivo)

        if resultado.get("erro"):
            return render(request, self.template_name, {"error": resultado["erro"]})

        dados = resultado["dados"]
        resumo = resultado["resumo"]

        if not dados:
            return render(
                request,
                self.template_name,
                {"error": "Nenhum registro encontrado no arquivo."},
            )

        # Valida os dados
        dados = validar_dados_relatorio(dados, request.user)

        # Serializa dados para a sessão (datas como string)
        dados_serializados = []
        for item in dados:
            item_copy = item.copy()
            item_copy["data"] = item["data"].isoformat()
            item_copy["valor"] = str(item["valor"])
            dados_serializados.append(item_copy)

        # Armazena na sessão
        request.session["importar_relatorio_dados"] = dados_serializados
        request.session["importar_relatorio_resumo"] = {
            "total_receitas": str(resumo["total_receitas"]),
            "total_despesas": str(resumo["total_despesas"]),
            "saldo": str(resumo["saldo"]),
            "quantidade": resumo["quantidade"],
        }

        return redirect("importar_relatorio_preview")


@method_decorator(login_required, name="dispatch")
class ImportarRelatorioPreviewView(View):
    """Preview dos dados a serem importados."""

    template_name = "importar_relatorio_preview.html"

    def get(self, request):
        from datetime import date
        from decimal import Decimal

        dados_serializados = request.session.get("importar_relatorio_dados")
        resumo_serializado = request.session.get("importar_relatorio_resumo")

        if not dados_serializados:
            messages.error(request, "Nenhum arquivo carregado. Faça o upload primeiro.")
            return redirect("importar_relatorio")

        # Deserializa os dados
        dados = []
        for item in dados_serializados:
            item_copy = item.copy()
            item_copy["data"] = date.fromisoformat(item["data"])
            item_copy["valor"] = Decimal(item["valor"])
            dados.append(item_copy)

        resumo = {
            "total_receitas": Decimal(resumo_serializado["total_receitas"]),
            "total_despesas": Decimal(resumo_serializado["total_despesas"]),
            "saldo": Decimal(resumo_serializado["saldo"]),
            "quantidade": resumo_serializado["quantidade"],
        }

        return render(request, self.template_name, {"dados": dados, "resumo": resumo})

    def post(self, request):
        from datetime import date
        from decimal import Decimal
        from core.services.import_report_service import importar_dados_relatorio

        # Verifica se é confirmação
        if not request.POST.get("confirmar"):
            return redirect("importar_relatorio")

        dados_serializados = request.session.get("importar_relatorio_dados")
        resumo_serializado = request.session.get("importar_relatorio_resumo")

        if not dados_serializados:
            messages.error(request, "Sessão expirada. Faça o upload novamente.")
            return redirect("importar_relatorio")

        # Valida senha
        password = request.POST.get("password")
        if not password:
            # Deserializa para re-renderizar
            dados = []
            for item in dados_serializados:
                item_copy = item.copy()
                item_copy["data"] = date.fromisoformat(item["data"])
                item_copy["valor"] = Decimal(item["valor"])
                dados.append(item_copy)

            resumo = {
                "total_receitas": Decimal(resumo_serializado["total_receitas"]),
                "total_despesas": Decimal(resumo_serializado["total_despesas"]),
                "saldo": Decimal(resumo_serializado["saldo"]),
                "quantidade": resumo_serializado["quantidade"],
            }

            return render(
                request,
                self.template_name,
                {"dados": dados, "resumo": resumo, "error": "A senha é obrigatória."},
            )

        # Autentica o usuário
        user = authenticate(username=request.user.username, password=password)
        if not user:
            dados = []
            for item in dados_serializados:
                item_copy = item.copy()
                item_copy["data"] = date.fromisoformat(item["data"])
                item_copy["valor"] = Decimal(item["valor"])
                dados.append(item_copy)

            resumo = {
                "total_receitas": Decimal(resumo_serializado["total_receitas"]),
                "total_despesas": Decimal(resumo_serializado["total_despesas"]),
                "saldo": Decimal(resumo_serializado["saldo"]),
                "quantidade": resumo_serializado["quantidade"],
            }

            return render(
                request,
                self.template_name,
                {"dados": dados, "resumo": resumo, "error": "Senha incorreta."},
            )

        # Deserializa os dados
        dados = []
        for item in dados_serializados:
            item_copy = item.copy()
            item_copy["data"] = date.fromisoformat(item["data"])
            item_copy["valor"] = Decimal(item["valor"])
            dados.append(item_copy)

        # Importa os dados
        modo = request.POST.get("modo", "criar")
        resultado = importar_dados_relatorio(dados, request.user, modo)

        # Limpa a sessão
        del request.session["importar_relatorio_dados"]
        del request.session["importar_relatorio_resumo"]

        if resultado.get("erro"):
            messages.error(request, f"Erro na importação: {resultado['erro']}")
            return redirect("importar_relatorio")

        # Monta mensagem de sucesso
        msg_parts = []
        if resultado["criados"] > 0:
            msg_parts.append(f"{resultado['criados']} registro(s) criado(s)")
        if resultado["atualizados"] > 0:
            msg_parts.append(f"{resultado['atualizados']} registro(s) atualizado(s)")
        if resultado["ignorados"] > 0:
            msg_parts.append(f"{resultado['ignorados']} registro(s) ignorado(s)")

        msg = "Importação concluída! " + ", ".join(msg_parts) + "."
        messages.success(request, msg)

        return redirect("transacoes")
