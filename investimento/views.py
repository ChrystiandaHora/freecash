from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Ativo, Transacao, ClasseAtivo, SubcategoriaAtivo
from .calculators import atualizar_cotacoes
from .forms import AtivoForm, TransacaoForm, ClasseAtivoForm


# ==========================
# CLASSES DE ATIVOS
# ==========================


@login_required
def classe_listar(request):
    classes = ClasseAtivo.objects.filter(usuario=request.user)
    return render(
        request, "investimento/classes/classe_list.html", {"classes": classes}
    )


@login_required
def classe_criar(request):
    form = ClasseAtivoForm(request.POST or None)
    if form.is_valid():
        classe = form.save(commit=False)
        classe.usuario = request.user
        classe.save()
        messages.success(request, "Classe criada com sucesso!")
        return redirect("investimento:classe_listar")
    return render(request, "investimento/classes/classe_form.html", {"form": form})


@login_required
def classe_editar(request, pk):
    classe = get_object_or_404(ClasseAtivo, pk=pk, usuario=request.user)
    form = ClasseAtivoForm(request.POST or None, instance=classe)
    if form.is_valid():
        form.save()
        messages.success(request, "Classe atualizada!")
        return redirect("investimento:classe_listar")
    return render(request, "investimento/classes/classe_form.html", {"form": form})


@login_required
def classe_excluir(request, pk):
    classe = get_object_or_404(ClasseAtivo, pk=pk, usuario=request.user)
    if request.method == "POST":
        classe.delete()
        messages.success(request, "Classe excluída!")
        return redirect("investimento:classe_listar")
    return render(
        request, "investimento/classes/classe_confirm_delete.html", {"classe": classe}
    )


@login_required
def dashboard(request):
    from .services.dashboard_service import DashboardInvestimentoService

    # Obtain the page number from request
    page_number = request.GET.get("page", 1)

    # Initialize service and retrieve context
    service = DashboardInvestimentoService(request.user)
    context = service.obter_dados_dashboard(page_number)

    return render(request, "investimento/dashboard/dashboard.html", context)


# ==========================
# ATIVOS
# ==========================


@login_required
def ativo_listar(request):
    ativos = Ativo.objects.filter(usuario=request.user)
    return render(request, "investimento/ativos/ativo_list.html", {"ativos": ativos})


@login_required
def ativo_criar(request):
    form = AtivoForm(request.POST or None)
    # Filtrar subcategorias do usuário
    form.fields["subcategoria"].queryset = SubcategoriaAtivo.objects.filter(
        usuario=request.user
    ).select_related("categoria__classe")

    if form.is_valid():
        ativo = form.save(commit=False)
        ativo.usuario = request.user
        ativo.save()
        form.process_initial_position(ativo)  # Processa transação inicial
        messages.success(request, "Ativo criado com sucesso!")
        return redirect("investimento:ativo_listar")

    # Build Hierarchy Data for Dependent Dropdowns
    classes = ClasseAtivo.objects.filter(usuario=request.user).prefetch_related(
        "categorias__subcategorias"
    )
    hierarchy = []
    for c in classes:
        cats_data = []
        for cat in c.categorias.all():
            subs_data = []
            for sub in cat.subcategorias.all():
                subs_data.append({"id": sub.id, "nome": sub.nome})
            cats_data.append(
                {"id": cat.id, "nome": cat.nome, "subcategorias": subs_data}
            )
        hierarchy.append({"id": c.id, "nome": c.nome, "categorias": cats_data})

    return render(
        request,
        "investimento/ativos/ativo_form.html",
        {"form": form, "hierarchy_data": hierarchy},
    )


@login_required
def ativo_editar(request, pk):
    ativo = get_object_or_404(Ativo, pk=pk, usuario=request.user)
    form = AtivoForm(request.POST or None, instance=ativo)
    # Filtrar subcategorias do usuário
    form.fields["subcategoria"].queryset = SubcategoriaAtivo.objects.filter(
        usuario=request.user
    ).select_related("categoria__classe")

    if form.is_valid():
        form.save()
        messages.success(request, "Ativo atualizado!")
        return redirect("investimento:ativo_listar")

    # Build Hierarchy Data for Dependent Dropdowns
    classes = ClasseAtivo.objects.filter(usuario=request.user).prefetch_related(
        "categorias__subcategorias"
    )
    hierarchy = []
    for c in classes:
        cats_data = []
        for cat in c.categorias.all():
            subs_data = []
            for sub in cat.subcategorias.all():
                subs_data.append({"id": sub.id, "nome": sub.nome})
            cats_data.append(
                {"id": cat.id, "nome": cat.nome, "subcategorias": subs_data}
            )
        hierarchy.append({"id": c.id, "nome": c.nome, "categorias": cats_data})

    return render(
        request,
        "investimento/ativos/ativo_form.html",
        {"form": form, "hierarchy_data": hierarchy},
    )


@login_required
def ativo_excluir(request, pk):
    ativo = get_object_or_404(Ativo, pk=pk, usuario=request.user)
    if request.method == "POST":
        ativo.delete()
        messages.success(request, "Ativo excluído!")
        return redirect("investimento:ativo_listar")
    return render(
        request, "investimento/ativos/ativo_confirm_delete.html", {"ativo": ativo}
    )


@login_required
def atualizar_cotacoes_view(request):
    """
    View para disparar atualização manual de cotações.
    """
    count, errors = atualizar_cotacoes()

    if count > 0:
        messages.success(request, f"{count} cotações atualizadas com sucesso!")

    if errors:
        # Mostra os 3 primeiros erros para não poluir
        for err in errors[:3]:
            messages.warning(request, err)
        if len(errors) > 3:
            messages.warning(request, f"E mais {len(errors) - 3} erros...")

    if count == 0 and not errors:
        messages.info(
            request, "Nenhuma cotação nova encontrada ou nenhum ativo com ticker."
        )

    # Redireciona de volta para onde veio ou dashboard
    next_url = request.META.get("HTTP_REFERER", "investimento:dashboard")
    return redirect(next_url)


# ==========================
# TRANSAÇÕES
# ==========================


@login_required
def transacao_listar(request):
    transacoes = Transacao.objects.filter(usuario=request.user)
    return render(
        request,
        "investimento/transacoes/transacao_list.html",
        {"transacoes": transacoes},
    )


@login_required
def transacao_criar(request):
    form = TransacaoForm(request.POST or None)
    # Filtrar ativos do usuário no form
    form.fields["ativo"].queryset = Ativo.objects.filter(
        usuario=request.user, ativo=True
    )

    if form.is_valid():
        transacao = form.save(commit=False)
        transacao.usuario = request.user
        transacao.save()
        messages.success(request, "Transação registrada!")
        return redirect("investimento:transacao_listar")
    return render(
        request, "investimento/transacoes/transacao_form.html", {"form": form}
    )


@login_required
def transacao_editar(request, pk):
    t = get_object_or_404(Transacao, pk=pk, usuario=request.user)
    form = TransacaoForm(request.POST or None, instance=t)

    # Incluir ativos ativos + o ativo atual da transação (caso esteja inativo)
    ativos_qs = Ativo.objects.filter(usuario=request.user, ativo=True)
    if t.ativo_id:
        ativos_qs = ativos_qs | Ativo.objects.filter(pk=t.ativo_id)
    form.fields["ativo"].queryset = ativos_qs.distinct()

    if form.is_valid():
        form.save()
        messages.success(request, "Transação atualizada!")
        return redirect("investimento:transacao_listar")
    return render(
        request, "investimento/transacoes/transacao_form.html", {"form": form}
    )


@login_required
def transacao_excluir(request, pk):
    t = get_object_or_404(Transacao, pk=pk, usuario=request.user)
    if request.method == "POST":
        t.delete()
        messages.success(request, "Transação excluída!")
        return redirect("investimento:transacao_listar")
    return render(
        request, "investimento/transacoes/transacao_confirm_delete.html", {"object": t}
    )
