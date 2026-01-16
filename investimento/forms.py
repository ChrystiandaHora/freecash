from django import forms
from .models import Ativo, Transacao, ClasseAtivo


class ClasseAtivoForm(forms.ModelForm):
    class Meta:
        model = ClasseAtivo
        fields = ["nome", "ativa"]


class AtivoForm(forms.ModelForm):
    class Meta:
        model = Ativo
        fields = ["ticker", "nome", "classe", "moeda", "ativo"]
        widgets = {
            "ticker": forms.TextInput(attrs={"class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "classe": forms.Select(attrs={"class": "form-select"}),
            "moeda": forms.TextInput(attrs={"class": "form-control"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


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
            # Calcula valor total automaticamente se não vier (mas o model exige, vamos setar no save do form se precisar, ou deixar o model calcular?
            # O ideal é o form calcular e mostrar, mas aqui vamos simplificar)
            # O model tem campo valor_total obrigatório.
            # Vamos calcular aqui.
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
