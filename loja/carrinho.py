"""Carrinho guardado na sessão do visitante: {produto_id: quantidade}."""
from decimal import Decimal

from .models import Produto

CHAVE = "carrinho"


class Carrinho:
    def __init__(self, request):
        self.session = request.session
        self.dados = self.session.setdefault(CHAVE, {})

    def _salvar(self):
        self.session.modified = True

    def adicionar(self, produto, quantidade=1):
        pid = str(produto.id)
        nova = self.dados.get(pid, 0) + quantidade
        self.dados[pid] = max(0, min(nova, produto.estoque))
        if self.dados[pid] == 0:
            del self.dados[pid]
        self._salvar()

    def definir(self, produto, quantidade):
        pid = str(produto.id)
        if quantidade <= 0:
            self.dados.pop(pid, None)
        else:
            self.dados[pid] = min(quantidade, produto.estoque)
        self._salvar()

    def remover(self, produto_id):
        self.dados.pop(str(produto_id), None)
        self._salvar()

    def limpar(self):
        self.session[CHAVE] = {}
        self._salvar()

    def itens(self):
        produtos = Produto.objects.filter(id__in=self.dados.keys(), ativo=True)
        for p in produtos:
            qtd = min(self.dados[str(p.id)], p.estoque)
            if qtd > 0:
                yield {"produto": p, "quantidade": qtd, "total": p.preco * qtd}

    def __len__(self):
        return sum(self.dados.values())

    @property
    def subtotal(self):
        return sum((i["total"] for i in self.itens()), Decimal("0"))
