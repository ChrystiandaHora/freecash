from django import forms
from django.utils import timezone
from .models import Ativo, Transacao, ClasseAtivo, SubcategoriaAtivo


class ClasseAtivoForm(forms.ModelForm):
    class Meta:
        model = ClasseAtivo
        fields = ["nome", "ativa"]


class AtivoForm(forms.ModelForm):
    # Campos Virtuais para Posição Inicial
    quantidade_inicial = forms.DecimalField(
        required=False,
        max_digits=19,
        decimal_places=8,
        label="Quantidade Inicial",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "0.00"}
        ),
        help_text="Preencha se já possui este ativo.",
    )
    preco_medio_inicial = forms.DecimalField(
        required=False,
        max_digits=19,
        decimal_places=4,
        label="Preço Pago (Unitário)",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "R$ 0.00"}
        ),
    )
    data_compra = forms.DateField(
        required=False,
        label="Data da Compra",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    # Campos Opcionais Renda Fixa (Definir required=False explicitamente)
    data_vencimento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    emissor = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    indexador = forms.ChoiceField(
        required=False,
        choices=Ativo.INDEXADOR_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    taxa = forms.DecimalField(
        required=False, widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = Ativo
        fields = [
            "ticker",
            "nome",
            "subcategoria",
            "data_vencimento",
            "emissor",
            "indexador",
            "taxa",
            "moeda",
            "ativo",
        ]
        widgets = {
            "ticker": forms.TextInput(attrs={"class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "subcategoria": forms.Select(attrs={"class": "form-select"}),
            "moeda": forms.TextInput(attrs={"class": "form-control"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_taxa(self):
        # Se vier vazio, retorna 0 (pois o model exige Decimal e não aceita None)
        return self.cleaned_data.get("taxa") or 0

    def process_initial_position(self, ativo):
        """
        Cria a transação inicial se os campos virtuais estiverem preenchidos.
        Deve ser chamado após o ativo ser salvo no banco.
        """
        qtd = self.cleaned_data.get("quantidade_inicial")
        preco = self.cleaned_data.get("preco_medio_inicial")
        data = self.cleaned_data.get("data_compra")

        if qtd and qtd > 0 and preco is not None:
            # Cria Transação de Compra Inicial
            Transacao.objects.create(
                usuario=ativo.usuario,
                ativo=ativo,
                tipo=Transacao.TIPO_COMPRA,
                data=data or timezone.now().date(),
                quantidade=qtd,
                preco_unitario=preco,
                valor_total=qtd * preco,
            )

    def save(self, commit=True):
        ativo = super().save(commit=False)
        if commit:
            ativo.save()
            self.process_initial_position(ativo)
        return ativo


class TransacaoForm(forms.ModelForm):
    class Meta:
        model = Transacao
        fields = ["ativo", "tipo", "data", "quantidade", "preco_unitario", "taxas"]
        widgets = {
            "ativo": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "quantidade": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.00000001"}
            ),
            "preco_unitario": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.0001"}
            ),
            "taxas": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        qtd = cleaned_data.get("quantidade")
        preco = cleaned_data.get("preco_unitario")
        taxas = cleaned_data.get("taxas") or 0

        if qtd and preco is not None:
            valor_bruto = qtd * preco
            tipo = cleaned_data.get("tipo")

            if tipo == Transacao.TIPO_COMPRA:
                cleaned_data["valor_total"] = valor_bruto + taxas
            elif tipo == Transacao.TIPO_VENDA:
                cleaned_data["valor_total"] = valor_bruto - taxas
            else:
                # Dividendo
                cleaned_data["valor_total"] = valor_bruto

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.valor_total = self.cleaned_data.get("valor_total")
        if commit:
            instance.save()
        return instance
