from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from core.services.import_planilha import importar_planilha_excel


@method_decorator(login_required, name="dispatch")
class ImportarView(View):
    def get(self, request):
        return render(request, "importar.html")

    def post(self, request):
        arquivo = request.FILES.get("arquivo")

        if not arquivo:
            messages.error(request, "Selecione um arquivo Excel para importar.")
            return redirect("importar")

        try:
            importar_planilha_excel(arquivo, request.user)
            messages.success(request, "Planilha importada com sucesso.")
            return redirect("dashboard")

        except Exception as e:
            messages.error(request, f"Erro ao importar arquivo: {str(e)}")
            return redirect("importar")
