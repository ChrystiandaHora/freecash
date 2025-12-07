from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View

from core.services.exportar_planilha import gerar_backup_excel


@method_decorator(login_required, name="dispatch")
class LogoutComExportacaoView(View):
    def get(self, request):
        response = gerar_backup_excel(request.user)
        logout(request)
        return response
