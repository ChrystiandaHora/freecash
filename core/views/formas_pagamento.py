from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from core.models import FormaPagamento


@method_decorator(login_required, name="dispatch")
class FormasPagamentoView(View):
    template_name = "formas_pagamento.html"

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        formas = FormaPagamento.objects.filter(usuario=request.user)
        if q:
            formas = formas.filter(nome__icontains=q)
        formas = formas.order_by("-ativa", "nome")
        return render(request, self.template_name, {"formas": formas, "q": q})

    def post(self, request):
        nome = (request.POST.get("nome") or "").strip()

        if not nome:
            messages.error(request, "Informe o nome da forma de pagamento.")
            return redirect("formas_pagamento")  # troque pelo name da sua rota

        try:
            FormaPagamento.objects.create(usuario=request.user, nome=nome)
            messages.success(request, "Forma de pagamento cadastrada!")
        except Exception:
            messages.error(
                request,
                "Não foi possível cadastrar. Talvez já exista uma com esse nome.",
            )

        return redirect("formas_pagamento")


@method_decorator(login_required, name="dispatch")
class EditarFormaPagamentoView(View):
    template_name = "formas_pagamento_editar.html"

    def get(self, request, pk):
        forma = get_object_or_404(FormaPagamento, pk=pk, usuario=request.user)
        return render(request, self.template_name, {"forma": forma})

    def post(self, request, pk):
        forma = get_object_or_404(FormaPagamento, pk=pk, usuario=request.user)

        nome = (request.POST.get("nome") or "").strip()
        ativa = request.POST.get("ativa") == "on"

        if not nome:
            messages.error(request, "O nome é obrigatório.")
            return redirect("editar_forma_pagamento", pk=forma.pk)

        # não permitir duplicado (tirando o próprio registro)
        if (
            FormaPagamento.objects.filter(usuario=request.user, nome__iexact=nome)
            .exclude(pk=forma.pk)
            .exists()
        ):
            messages.error(request, "Já existe outra forma de pagamento com esse nome.")
            return redirect("editar_forma_pagamento", pk=forma.pk)

        forma.nome = nome
        forma.ativa = ativa
        forma.save()

        messages.success(request, "Forma de pagamento atualizada!")
        return redirect("formas_pagamento")
