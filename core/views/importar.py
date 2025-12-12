from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages

from core.services.importar_unificado import importar_planilha_unificada


class ImportarView(View):
    template_name = "importar.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        arquivo = request.FILES.get("arquivo")

        if not arquivo:
            messages.error(request, "Selecione um arquivo para importar.")
            return redirect("importar")

        try:
            importar_planilha_unificada(arquivo, request.user)
            messages.success(request, "Importação concluída com sucesso!")
            return redirect("dashboard")

        except Exception as erro:
            messages.error(request, f"Falha na importação: {erro}")
            return redirect("importar")
