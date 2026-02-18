from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime

from core.models import ConfigUsuario


def parse_date(date_str: str):
    """Parse date string in YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


@method_decorator(login_required, name="dispatch")
class ExportarView(View):
    template_name = "core/servicos/exportar.html"

    def get(self, request):
        config = ConfigUsuario.objects.filter(usuario=request.user).first()
        return render(request, self.template_name, {"config": config})

    def post(self, request):
        password = request.POST.get("password")

        if not password:
            return render(
                request,
                self.template_name,
                {
                    "config": ConfigUsuario.objects.filter(
                        usuario=request.user
                    ).first(),
                    "error": "A senha é obrigatória para gerar o backup seguro (.fcbk).",
                },
            )

        from core.services.export_service import export_user_data

        # Modular dynamic backup
        encrypted_payload = export_user_data(request.user, password)

        filename = f"backup_freecash_{request.user.username}_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.fcbk"

        response = HttpResponse(
            encrypted_payload, content_type="application/octet-stream"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Update last export date
        config, _ = ConfigUsuario.objects.get_or_create(usuario=request.user)
        config.ultimo_export_em = timezone.now()
        config.save(update_fields=["ultimo_export_em"])

        return response


@method_decorator(login_required, name="dispatch")
class ExportarRelatorioView(View):
    """Exporta relatório de movimentações em PDF ou Excel."""

    template_name = "core/servicos/exportar_relatorio.html"

    def get(self, request):
        hoje = timezone.localdate()
        # Default: mês atual
        primeiro_dia = hoje.replace(day=1)

        return render(
            request,
            self.template_name,
            {
                "data_inicio": primeiro_dia.strftime("%Y-%m-%d"),
                "data_fim": hoje.strftime("%Y-%m-%d"),
            },
        )

    def post(self, request):
        data_inicio_str = request.POST.get("data_inicio", "")
        data_fim_str = request.POST.get("data_fim", "")
        formato = request.POST.get("formato", "excel")

        data_inicio = parse_date(data_inicio_str)
        data_fim = parse_date(data_fim_str)

        if not data_inicio or not data_fim:
            return render(
                request,
                self.template_name,
                {
                    "error": "Datas inválidas. Use o formato correto.",
                    "data_inicio": data_inicio_str,
                    "data_fim": data_fim_str,
                },
            )

        if data_inicio > data_fim:
            return render(
                request,
                self.template_name,
                {
                    "error": "A data de início deve ser anterior à data de fim.",
                    "data_inicio": data_inicio_str,
                    "data_fim": data_fim_str,
                },
            )

        from core.services.export_report_service import gerar_excel, gerar_pdf

        timestamp_inicio = data_inicio.strftime("%d-%m-%Y")
        timestamp_fim = data_fim.strftime("%d-%m-%Y")
        base_filename = f"Relatório Financeiro {timestamp_inicio} a {timestamp_fim}"

        if formato == "pdf":
            content = gerar_pdf(request.user, data_inicio, data_fim)
            filename = f"{base_filename}.pdf"
            content_type = "application/pdf"
        else:
            content = gerar_excel(request.user, data_inicio, data_fim)
            filename = f"{base_filename}.xlsx"
            content_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response
