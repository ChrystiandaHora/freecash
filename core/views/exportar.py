from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from core.services.exportar_planilha import gerar_backup_excel
from core.models import ConfigUsuario


@method_decorator(login_required, name="dispatch")
class ExportarView(View):
    template_name = "exportar.html"

    def get(self, request):
        config = ConfigUsuario.objects.filter(usuario=request.user).first()
        return render(request, self.template_name, {"config": config})

    def post(self, request):
        return gerar_backup_excel(request.user)
