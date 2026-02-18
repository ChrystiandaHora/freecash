from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Ativo, Transacao, ClasseAtivo, SubcategoriaAtivo
from .services import atualizar_cotacoes
from .forms import AtivoForm, TransacaoForm, ClasseAtivoForm


# ==========================
# CLASSES DE ATIVOS
# ==========================


@login_required
def classe_listar(request):
    classes = ClasseAtivo.objects.filter(usuario=request.user)
    return render(request, "classe_list.html", {"classes": classes})


@login_required
def classe_criar(request):
    form = ClasseAtivoForm(request.POST or None)
    if form.is_valid():
        classe = form.save(commit=False)
        classe.usuario = request.user
        classe.save()
        messages.success(request, "Classe criada com sucesso!")
        return redirect("investimento:classe_listar")
    return render(request, "classe_form.html", {"form": form})


@login_required
def classe_editar(request, pk):
    classe = get_object_or_404(ClasseAtivo, pk=pk, usuario=request.user)
    form = ClasseAtivoForm(request.POST or None, instance=classe)
    if form.is_valid():
        form.save()
        messages.success(request, "Classe atualizada!")
        return redirect("investimento:classe_listar")
    return render(request, "classe_form.html", {"form": form})


@login_required
def classe_excluir(request, pk):
    classe = get_object_or_404(ClasseAtivo, pk=pk, usuario=request.user)
    if request.method == "POST":
        classe.delete()
        messages.success(request, "Classe excluída!")
        return redirect("investimento:classe_listar")
    return render(request, "classe_confirm_delete.html", {"classe": classe})


@login_required
def dashboard(request):
    from datetime import date, timedelta

    ativos = (
        Ativo.objects.filter(usuario=request.user, ativo=True)
        .select_related("subcategoria__categoria__classe")
        .order_by("subcategoria__categoria__classe__nome", "ticker")
    )

    # Convert to list to persist attributes set in loop
    ativos = list(ativos)

    # Calculate portfolio value and build allocation data
    total_patrimonio = 0
    total_investido = 0
    allocation_by_class = {}
    allocation_by_category = {}

    for a in ativos:
        # Calcula valores usando as properties do model (que buscam cotação)
        # O ideal seria otimizar para evitar N+1 queries de cotação com prefetch,
        # mas por simplicidade usaremos as properties por enquanto.
        val_atual = a.valor_total_atual
        val_investido = a.valor_investido

        # Injeta no objeto para uso no template sem recalcular
        a.cached_valor_atual = val_atual
        a.cached_rentabilidade = a.rentabilidade
        a.cached_rentabilidade_percentual = a.rentabilidade_percentual

        total_patrimonio += val_atual
        total_investido += val_investido

        # Aggregate by Class
        if (
            a.subcategoria
            and a.subcategoria.categoria
            and a.subcategoria.categoria.classe
        ):
            class_name = a.subcategoria.categoria.classe.nome
            cat_name = a.subcategoria.categoria.nome
        else:
            class_name = "Sem Classe"
            cat_name = "Sem Categoria"

        allocation_by_class[class_name] = allocation_by_class.get(
            class_name, 0
        ) + float(val_atual)
        allocation_by_category[cat_name] = allocation_by_category.get(
            cat_name, 0
        ) + float(val_atual)

    allocation_labels = list(allocation_by_class.keys())
    allocation_values = list(allocation_by_class.values())
    category_labels = list(allocation_by_category.keys())
    category_values = list(allocation_by_category.values())

    # Top 5 ativos by value
    ativos_with_value = list(ativos)
    ativos_with_value.sort(key=lambda x: x.cached_valor_atual, reverse=True)
    top_5_ativos = ativos_with_value[:5]

    for a in top_5_ativos:
        if total_patrimonio > 0:
            a.percentual = (float(a.cached_valor_atual) / float(total_patrimonio)) * 100
        else:
            a.percentual = 0

    # Top Ativos by Rentabilidade
    # Clone list to sort by profitability
    ativos_by_rent = list(ativos)
    ativos_by_rent.sort(key=lambda x: x.cached_rentabilidade, reverse=True)
    top_rentabilidade = ativos_by_rent[:5]

    # Última transação
    ultima_transacao = (
        Transacao.objects.filter(ativo__usuario=request.user).order_by("-data").first()
    )

    # Próximos vencimentos (Renda Fixa com data_vencimento nos próximos 90 dias)
    today = date.today()
    limit_date = today + timedelta(days=90)
    proximos_vencimentos = (
        Ativo.objects.filter(
            usuario=request.user,
            ativo=True,
            data_vencimento__gte=today,
            data_vencimento__lte=limit_date,
        )
        .select_related("subcategoria__categoria__classe")
        .order_by("data_vencimento")[:5]
    )

    # Prepare for pagination of the full list
    # Use request.GET.get('page') or 1
    paginator = Paginator(ativos, 5)
    page_number = request.GET.get("page")
    ativos_page = paginator.get_page(page_number)

    # Rentabilidade Global (Incluindo Realizados e Dividendos)
    transacoes_todas = Transacao.objects.filter(usuario=request.user)
    total_compras = transacoes_todas.filter(tipo=Transacao.TIPO_COMPRA).aggregate(
        total=Sum("valor_total")
    )["total"] or Decimal(0)
    total_vendas = transacoes_todas.filter(tipo=Transacao.TIPO_VENDA).aggregate(
        total=Sum("valor_total")
    )["total"] or Decimal(0)
    total_dividendos = transacoes_todas.filter(tipo=Transacao.TIPO_DIVIDENDO).aggregate(
        total=Sum("valor_total")
    )["total"] or Decimal(0)

    # Rentabilidade Total = (Patrimônio Atual + Vendas + Dividendos) - Compras
    total_rentabilidade = (
        Decimal(total_patrimonio) + total_vendas + total_dividendos
    ) - total_compras
    total_rentabilidade_percentual = 0
    if total_compras > 0:
        total_rentabilidade_percentual = (total_rentabilidade / total_compras) * 100

    context = {
        "ativos": ativos,  # Keep full list for charts
        "ativos_page": ativos_page,  # Paginated list for table
        "total_patrimonio": total_patrimonio,
        "total_investido": total_investido,
        "total_rentabilidade": float(total_rentabilidade),
        "total_rentabilidade_percentual": float(total_rentabilidade_percentual),
        "total_dividendos": float(total_dividendos),
        "allocation_labels": allocation_labels,
        "allocation_values": allocation_values,
        "allocation_data": list(zip(allocation_labels, allocation_values)),
        "category_labels": category_labels,
        "category_values": category_values,
        "category_data": list(zip(category_labels, category_values)),
        "top_5_ativos": top_5_ativos,
        "top_rentabilidade": top_rentabilidade,
        "ultima_transacao": ultima_transacao,
        "proximos_vencimentos": proximos_vencimentos,
    }
    return render(request, "investimento/dashboard.html", context)


# ==========================
# ATIVOS
# ==========================


@login_required
def ativo_listar(request):
    ativos = Ativo.objects.filter(usuario=request.user)
    return render(request, "ativo_list.html", {"ativos": ativos})


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
        "ativo_form.html",
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
        "ativo_form.html",
        {"form": form, "hierarchy_data": hierarchy},
    )


@login_required
def ativo_excluir(request, pk):
    ativo = get_object_or_404(Ativo, pk=pk, usuario=request.user)
    if request.method == "POST":
        ativo.delete()
        messages.success(request, "Ativo excluído!")
        return redirect("investimento:ativo_listar")
    return render(request, "ativo_confirm_delete.html", {"ativo": ativo})


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
    return render(request, "transacao_list.html", {"transacoes": transacoes})


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
    return render(request, "transacao_form.html", {"form": form})


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
    return render(request, "transacao_form.html", {"form": form})


@login_required
def transacao_excluir(request, pk):
    t = get_object_or_404(Transacao, pk=pk, usuario=request.user)
    if request.method == "POST":
        t.delete()
        messages.success(request, "Transação excluída!")
        return redirect("investimento:transacao_listar")
    return render(request, "transacao_confirm_delete.html", {"object": t})
