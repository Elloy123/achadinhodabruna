from django import forms

from .models import Pedido


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ["nome", "email", "telefone", "tipo_entrega", "endereco", "bairro", "referencia", "observacoes"]
        labels = {
            "nome": "Nome completo",
            "email": "E-mail",
            "telefone": "WhatsApp",
            "tipo_entrega": "Como quer receber?",
            "endereco": "Rua e número",
            "bairro": "Bairro",
            "referencia": "Ponto de referência",
            "observacoes": "Observações",
        }
        widgets = {
            "tipo_entrega": forms.RadioSelect,
            "telefone": forms.TextInput(attrs={"placeholder": "(93) 9 0000-0000", "inputmode": "tel"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        dados = super().clean()
        if dados.get("tipo_entrega") == Pedido.TipoEntrega.ENTREGA:
            for campo in ("endereco", "bairro"):
                if not dados.get(campo):
                    self.add_error(campo, "Obrigatório para entrega em Rurópolis.")
        return dados
