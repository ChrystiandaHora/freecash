from django import forms
from core.models import Conta, Categoria, FormaPagamento, CartaoCredito, CategoriaCartao


class ContaForm(forms.ModelForm):
    MOEDA_CHOICES = [
        ("BRL", "🇧🇷 BRL (R$)"),
        ("USD", "🇺🇸 USD (US$)"),
        ("EUR", "🇪🇺 EUR (€)"),
        ("GBP", "🇬🇧 GBP (£)"),
    ]

    # Campos que atuam fora da estrutura padrão
    moeda = forms.ChoiceField(choices=MOEDA_CHOICES, required=False, initial="BRL")
    parcelado = forms.BooleanField(required=False)
    numero_parcelas = forms.IntegerField(
        required=False, min_value=2, max_value=24, initial=2
    )
    multiplicar = forms.BooleanField(required=False)
    numero_multiplicacoes = forms.IntegerField(
        required=False, min_value=2, max_value=120, initial=2
    )
    data_limite_repeticao = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    pago = forms.BooleanField(required=False)
    atualizar_futuros = forms.BooleanField(required=False, initial=False)

    class Meta:
        model = Conta
        fields = [
            "descricao",
            "valor",
            "data_prevista",
            "categoria",
            "forma_pagamento",
            "categoria_cartao",
        ]
        widgets = {
            "data_prevista": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop("usuario", None)
        self.tipo_conta = kwargs.pop("tipo", Conta.TIPO_DESPESA)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["pago"].initial = self.instance.transacao_realizada

        if self.usuario:
            self.fields["categoria"].queryset = Categoria.objects.filter(
                usuario=self.usuario, tipo=self.tipo_conta
            ).order_by("nome")
            self.fields["forma_pagamento"].queryset = FormaPagamento.objects.filter(
                usuario=self.usuario, ativa=True
            ).order_by("nome")
            self.fields[
                "categoria_cartao"
            ].queryset = CategoriaCartao.objects.all().order_by("nome")

    def clean(self):
        cleaned_data = super().clean()
        parcelado = cleaned_data.get("parcelado")
        multiplicar = cleaned_data.get("multiplicar")

        if parcelado and multiplicar:
            self.add_error(None, "Escolha apenas uma opção: parcelar ou multiplicar.")
        return cleaned_data


class CartaoCreditoForm(forms.ModelForm):
    class Meta:
        model = CartaoCredito
        fields = [
            "nome",
            "bandeira",
            "ultimos_digitos",
            "limite",
            "dia_fechamento",
            "dia_vencimento",
        ]

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop("usuario", None)
        super().__init__(*args, **kwargs)

    def clean_limite(self):
        limite_raw = self.data.get("limite") or ""
        limite_raw = limite_raw.strip()
        if not limite_raw:
            return None

        try:
            if "," in limite_raw:
                limite_raw = limite_raw.replace(".", "").replace(",", ".")
            return forms.DecimalField().clean(limite_raw)
        except Exception:
            raise forms.ValidationError("Limite inválido.")
