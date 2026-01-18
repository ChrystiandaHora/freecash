from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import ConfigUsuario


@method_decorator(login_required, name="dispatch")
class ExportarView(View):
    template_name = "exportar.html"

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
        from django.http import HttpResponse

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
