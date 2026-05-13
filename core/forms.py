from django import forms
from core.models import Conta, Categoria, CartaoCredito


class ContaForm(forms.ModelForm):
    # Campos que atuam fora da estrutura padrão
    pago = forms.BooleanField(required=False)
    atualizar_futuros = forms.BooleanField(required=False, initial=False)

    class Meta:
        model = Conta
        fields = [
            "descricao",
            "valor",
            "data_prevista",
            "categoria",
        ]
        widgets = {
            "data_prevista": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop("usuario", None)
        self.tipo_conta = kwargs.pop("tipo", Conta.TIPO_DESPESA)
        super().__init__(*args, **kwargs)
        self.fields["categoria"].required = False
        
        if self.instance and self.instance.pk:
            self.fields["pago"].initial = self.instance.transacao_realizada

        if self.usuario:
            self.fields["categoria"].queryset = Categoria.objects.filter(
                usuario=self.usuario, tipo=self.tipo_conta
            ).order_by("nome")

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Garante que o tipo da conta seja definido
        if not instance.tipo:
            instance.tipo = self.tipo_conta

        if not instance.categoria and self.usuario:
            # Busca a categoria padrão para o tipo (R=Receita, D=Gastos)
            default_cat = Categoria.objects.filter(
                usuario=self.usuario, 
                tipo=self.tipo_conta,
                is_default=True
            ).first()
            if default_cat:
                instance.categoria = default_cat
        
        if commit:
            instance.save()
        return instance


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
