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
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "dd/mm/aaaa"}
        ),
    )

    # Campos Opcionais Renda Fixa (Definir required=False explicitamente)
    data_vencimento = forms.DateField(
        required=False,
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "dd/mm/aaaa"}
        ),
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
    # Campo virtual para dividendos
    valor_dividendo = forms.DecimalField(
        required=False,
        max_digits=19,
        decimal_places=2,
        label="Valor Recebido",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "placeholder": "R$ 0,00"}
        ),
    )

    class Meta:
        model = Transacao
        fields = ["ativo", "tipo", "data", "quantidade", "preco_unitario", "taxas"]
        widgets = {
            "ativo": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "data": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "dd/mm/aaaa"}
            ),
            "quantidade": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.00000001"}
            ),
            "preco_unitario": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.0001"}
            ),
            "taxas": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Accept DD/MM/YYYY format for date field
        self.fields["data"].input_formats = ["%d/%m/%Y", "%Y-%m-%d"]
        # Campos não são required por padrão (JS controla dinamicamente)
        self.fields["quantidade"].required = False
        self.fields["preco_unitario"].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")

        if tipo == Transacao.TIPO_DIVIDENDO:
            # Para dividendos, usamos o valor_dividendo
            valor = cleaned_data.get("valor_dividendo")
            if not valor:
                raise forms.ValidationError("Informe o valor do dividendo recebido.")

            # Definimos quantidade=1 e preco=valor para manter compatibilidade
            cleaned_data["quantidade"] = 1
            cleaned_data["preco_unitario"] = valor
            cleaned_data["valor_total"] = valor
            cleaned_data["taxas"] = 0
        else:
            # Compra/Venda: valida quantidade e preço
            qtd = cleaned_data.get("quantidade")
            preco = cleaned_data.get("preco_unitario")
            taxas = cleaned_data.get("taxas") or 0

            if not qtd or qtd <= 0:
                raise forms.ValidationError("Informe a quantidade.")
            if preco is None or preco < 0:
                raise forms.ValidationError("Informe o preço unitário.")

            valor_bruto = qtd * preco

            if tipo == Transacao.TIPO_COMPRA:
                cleaned_data["valor_total"] = valor_bruto + taxas
            elif tipo == Transacao.TIPO_VENDA:
                cleaned_data["valor_total"] = valor_bruto - taxas

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.quantidade = self.cleaned_data.get("quantidade")
        instance.preco_unitario = self.cleaned_data.get("preco_unitario")
        instance.taxas = self.cleaned_data.get("taxas") or 0
        instance.valor_total = self.cleaned_data.get("valor_total")
        if commit:
            instance.save()
        return instance
