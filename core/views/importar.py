from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from core.models import LogImportacao
from core.services.import_service import importar_planilha_unificada


@method_decorator(login_required, name="dispatch")
class ImportarView(View):
    template_name = "importar.html"

    def get(self, request):
        logs = LogImportacao.objects.filter(usuario=request.user).order_by(
            "-criada_em"
        )[:20]
        return render(request, self.template_name, {"logs": logs})

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
            resultado = importar_planilha_unificada(
                arquivo, request.user, sobrescrever=True, password=password
            )
            messages.success(
                request, resultado.get("msg") or "Importação concluída com sucesso!"
            )
            return redirect("importar")
        except Exception as e:
            messages.error(request, f"Falha na importação: {e}")
            return redirect("importar")
