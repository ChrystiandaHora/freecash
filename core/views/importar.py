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
            ler_excel_investimentos,
            ler_excel_transacoes_investimento,
            validar_dados_investimentos,
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

        # Lê o arquivo Excel - Movimentações
        resultado = ler_excel_relatorio(arquivo)

        if resultado.get("erro"):
            return render(request, self.template_name, {"error": resultado["erro"]})

        dados = resultado["dados"]
        resumo = resultado["resumo"]

        # Valida os dados de movimentações
        if dados:
            dados = validar_dados_relatorio(dados, request.user)

        # Lê abas de investimentos
        arquivo.seek(0)
        resultado_invest = ler_excel_investimentos(arquivo)
        arquivo.seek(0)
        resultado_trans = ler_excel_transacoes_investimento(arquivo)

        dados_invest = resultado_invest.get("dados", [])
        resumo_invest = resultado_invest.get("resumo", {})
        dados_trans = resultado_trans.get("dados", [])
        resumo_trans = resultado_trans.get("resumo", {})

        # Valida dados de investimentos
        if dados_invest or dados_trans:
            dados_invest, dados_trans = validar_dados_investimentos(
                dados_invest, dados_trans, request.user
            )

        # Serializa dados de movimentações para a sessão
        dados_serializados = []
        for item in dados:
            item_copy = item.copy()
            item_copy["data"] = item["data"].isoformat()
            item_copy["valor"] = str(item["valor"])
            dados_serializados.append(item_copy)

        # Serializa dados de investimentos
        invest_serializados = []
        for item in dados_invest:
            item_copy = item.copy()
            item_copy["quantidade"] = str(item["quantidade"])
            item_copy["preco_medio"] = str(item["preco_medio"])
            item_copy["valor_posicao"] = str(item["valor_posicao"])
            invest_serializados.append(item_copy)

        # Serializa transações de investimentos
        trans_serializados = []
        for item in dados_trans:
            item_copy = item.copy()
            item_copy["data"] = item["data"].isoformat()
            item_copy["quantidade"] = str(item["quantidade"])
            item_copy["preco_unitario"] = str(item["preco_unitario"])
            item_copy["taxas"] = str(item["taxas"])
            item_copy["valor_total"] = str(item["valor_total"])
            trans_serializados.append(item_copy)

        # Armazena na sessão
        request.session["importar_relatorio_dados"] = dados_serializados
        request.session["importar_relatorio_resumo"] = {
            "total_receitas": str(resumo.get("total_receitas", 0)),
            "total_despesas": str(resumo.get("total_despesas", 0)),
            "saldo": str(resumo.get("saldo", 0)),
            "quantidade": resumo.get("quantidade", 0),
        }

        # Armazena investimentos na sessão
        request.session["importar_investimentos_dados"] = invest_serializados
        request.session["importar_investimentos_resumo"] = {
            "total_carteira": str(resumo_invest.get("total_carteira", 0)),
            "quantidade": resumo_invest.get("quantidade", 0),
        }

        # Armazena transações de investimento na sessão
        request.session["importar_transacoes_invest_dados"] = trans_serializados
        request.session["importar_transacoes_invest_resumo"] = {
            "total_compras": str(resumo_trans.get("total_compras", 0)),
            "total_vendas": str(resumo_trans.get("total_vendas", 0)),
            "total_proventos": str(resumo_trans.get("total_proventos", 0)),
            "quantidade": resumo_trans.get("quantidade", 0),
        }

        return redirect("importar_relatorio_preview")


@method_decorator(login_required, name="dispatch")
class ImportarRelatorioPreviewView(View):
    """Preview dos dados a serem importados."""

    template_name = "importar_relatorio_preview.html"

    def get(self, request):
        from datetime import date
        from decimal import Decimal

        dados_serializados = request.session.get("importar_relatorio_dados", [])
        resumo_serializado = request.session.get("importar_relatorio_resumo", {})
        invest_serializados = request.session.get("importar_investimentos_dados", [])
        resumo_invest_serializado = request.session.get(
            "importar_investimentos_resumo", {}
        )
        trans_serializados = request.session.get("importar_transacoes_invest_dados", [])
        resumo_trans_serializado = request.session.get(
            "importar_transacoes_invest_resumo", {}
        )

        # Verifica se há qualquer dado
        if (
            not dados_serializados
            and not invest_serializados
            and not trans_serializados
        ):
            messages.error(request, "Nenhum arquivo carregado. Faça o upload primeiro.")
            return redirect("importar_relatorio")

        # Deserializa movimentações
        dados = []
        for item in dados_serializados:
            item_copy = item.copy()
            item_copy["data"] = date.fromisoformat(item["data"])
            item_copy["valor"] = Decimal(item["valor"])
            dados.append(item_copy)

        resumo = {
            "total_receitas": Decimal(resumo_serializado.get("total_receitas", "0")),
            "total_despesas": Decimal(resumo_serializado.get("total_despesas", "0")),
            "saldo": Decimal(resumo_serializado.get("saldo", "0")),
            "quantidade": resumo_serializado.get("quantidade", 0),
        }

        # Deserializa investimentos
        dados_invest = []
        for item in invest_serializados:
            item_copy = item.copy()
            item_copy["quantidade"] = Decimal(item["quantidade"])
            item_copy["preco_medio"] = Decimal(item["preco_medio"])
            item_copy["valor_posicao"] = Decimal(item["valor_posicao"])
            dados_invest.append(item_copy)

        resumo_invest = {
            "total_carteira": Decimal(
                resumo_invest_serializado.get("total_carteira", "0")
            ),
            "quantidade": resumo_invest_serializado.get("quantidade", 0),
        }

        # Deserializa transações de investimento
        dados_trans = []
        for item in trans_serializados:
            item_copy = item.copy()
            item_copy["data"] = date.fromisoformat(item["data"])
            item_copy["quantidade"] = Decimal(item["quantidade"])
            item_copy["preco_unitario"] = Decimal(item["preco_unitario"])
            item_copy["taxas"] = Decimal(item["taxas"])
            item_copy["valor_total"] = Decimal(item["valor_total"])
            dados_trans.append(item_copy)

        resumo_trans = {
            "total_compras": Decimal(
                resumo_trans_serializado.get("total_compras", "0")
            ),
            "total_vendas": Decimal(resumo_trans_serializado.get("total_vendas", "0")),
            "total_proventos": Decimal(
                resumo_trans_serializado.get("total_proventos", "0")
            ),
            "quantidade": resumo_trans_serializado.get("quantidade", 0),
        }

        context = {
            "dados": dados,
            "resumo": resumo,
            "dados_invest": dados_invest,
            "resumo_invest": resumo_invest,
            "dados_trans": dados_trans,
            "resumo_trans": resumo_trans,
            "tem_investimentos": len(dados_invest) > 0 or len(dados_trans) > 0,
        }

        return render(request, self.template_name, context)

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

        # Limpa a sessão de movimentações
        if "importar_relatorio_dados" in request.session:
            del request.session["importar_relatorio_dados"]
        if "importar_relatorio_resumo" in request.session:
            del request.session["importar_relatorio_resumo"]

        if resultado.get("erro"):
            messages.error(request, f"Erro na importação: {resultado['erro']}")
            return redirect("importar_relatorio")

        # Importa investimentos se houver dados
        invest_serializados = request.session.get("importar_investimentos_dados", [])
        trans_serializados = request.session.get("importar_transacoes_invest_dados", [])

        resultado_invest = None
        if invest_serializados or trans_serializados:
            from core.services.import_report_service import importar_dados_investimentos

            # Deserializa investimentos
            dados_invest = []
            for item in invest_serializados:
                item_copy = item.copy()
                item_copy["quantidade"] = Decimal(item["quantidade"])
                item_copy["preco_medio"] = Decimal(item["preco_medio"])
                item_copy["valor_posicao"] = Decimal(item["valor_posicao"])
                dados_invest.append(item_copy)

            # Deserializa transações
            dados_trans = []
            for item in trans_serializados:
                item_copy = item.copy()
                item_copy["data"] = date.fromisoformat(item["data"])
                item_copy["quantidade"] = Decimal(item["quantidade"])
                item_copy["preco_unitario"] = Decimal(item["preco_unitario"])
                item_copy["taxas"] = Decimal(item["taxas"])
                item_copy["valor_total"] = Decimal(item["valor_total"])
                dados_trans.append(item_copy)

            resultado_invest = importar_dados_investimentos(
                dados_invest, dados_trans, request.user, modo
            )

        # Limpa sessões de investimentos
        if "importar_investimentos_dados" in request.session:
            del request.session["importar_investimentos_dados"]
        if "importar_investimentos_resumo" in request.session:
            del request.session["importar_investimentos_resumo"]
        if "importar_transacoes_invest_dados" in request.session:
            del request.session["importar_transacoes_invest_dados"]
        if "importar_transacoes_invest_resumo" in request.session:
            del request.session["importar_transacoes_invest_resumo"]

        # Monta mensagem de sucesso
        msg_parts = []
        if resultado["criados"] > 0:
            msg_parts.append(f"{resultado['criados']} movimentação(ões) criada(s)")
        if resultado["atualizados"] > 0:
            msg_parts.append(
                f"{resultado['atualizados']} movimentação(ões) atualizada(s)"
            )
        if resultado["ignorados"] > 0:
            msg_parts.append(f"{resultado['ignorados']} movimentação(ões) ignorada(s)")

        if resultado_invest:
            if resultado_invest.get("ativos_criados", 0) > 0:
                msg_parts.append(
                    f"{resultado_invest['ativos_criados']} ativo(s) criado(s)"
                )
            if resultado_invest.get("ativos_atualizados", 0) > 0:
                msg_parts.append(
                    f"{resultado_invest['ativos_atualizados']} ativo(s) atualizado(s)"
                )
            if resultado_invest.get("transacoes_criadas", 0) > 0:
                msg_parts.append(
                    f"{resultado_invest['transacoes_criadas']} transação(ões) de invest. criada(s)"
                )

        msg = (
            "Importação concluída! " + ", ".join(msg_parts) + "."
            if msg_parts
            else "Importação concluída!"
        )
        messages.success(request, msg)

        return redirect("transacoes")
