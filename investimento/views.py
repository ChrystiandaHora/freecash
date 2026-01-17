from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.contrib import messages
from .models import Ativo, Transacao, ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo
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
    ativos = Ativo.objects.filter(usuario=request.user, ativo=True).order_by(
        "subcategoria__categoria__classe__nome", "ticker"
    )

    # Calcular total investido e valor atual (se tivéssemos cotação online, mas vamos usar preço médio ou manual)
    # Por enquanto, dashboard mostra resumo da carteira baseada no custo de aquisição (preco_medio * qtd)

    total_patrimonio = 0
    allocation_by_class = {}

    for a in ativos:
        a.valor_atual = a.quantidade * a.preco_medio  # Simplificação: Valor 'Investido'
        total_patrimonio += a.valor_atual

        # Aggregate by Class for chart
        if (
            a.subcategoria
            and a.subcategoria.categoria
            and a.subcategoria.categoria.classe
        ):
            class_name = a.subcategoria.categoria.classe.nome
        else:
            class_name = "Sem Classe"
        allocation_by_class[class_name] = allocation_by_class.get(
            class_name, 0
        ) + float(a.valor_atual)

    allocation_labels = list(allocation_by_class.keys())
    allocation_values = list(allocation_by_class.values())

    context = {
        "ativos": ativos,
        "total_patrimonio": total_patrimonio,
        "allocation_labels": allocation_labels,
        "allocation_values": allocation_values,
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
    return render(request, "ativo_form.html", {"form": form})


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
    return render(request, "ativo_form.html", {"form": form})


@login_required
def ativo_excluir(request, pk):
    ativo = get_object_or_404(Ativo, pk=pk, usuario=request.user)
    if request.method == "POST":
        ativo.delete()
        messages.success(request, "Ativo excluído!")
        return redirect("investimento:ativo_listar")
    return render(request, "ativo_confirm_delete.html", {"ativo": ativo})


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
