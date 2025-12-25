from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from core.models import LogImportacao
from core.services.importar_unificado import importar_planilha_unificada


@method_decorator(login_required, name="dispatch")
class ImportarView(View):
    template_name = "importar.html"

    def get(self, request):
        logs = LogImportacao.objects.filter(usuario=request.user).order_by(
            "-criado_em"
        )[:20]

        return render(request, self.template_name, {"logs": logs})

    def post(self, request):
        arquivo = request.FILES.get("arquivo")

        if not arquivo:
            messages.error(request, "Selecione um arquivo para importar.")
            return redirect("importar")

        try:
            importar_planilha_unificada(arquivo, request.user)
            messages.success(request, "Importação concluída com sucesso!")
            return redirect(
                "importar"
            )  # melhor voltar pra tela de importação pra ver o log

        except Exception as erro:
            messages.error(request, f"Falha na importação: {erro}")
            return redirect("importar")
