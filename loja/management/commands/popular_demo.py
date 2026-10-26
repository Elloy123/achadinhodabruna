"""Cria categorias, produtos e histórico fictício de buscas/vendas para testar o painel.

Uso: python manage.py popular_demo [--limpar]
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from loja.models import Busca, Categoria, ItemPedido, Pedido, Produto

CATALOGO = {
    "Roupas": [("Vestido floral midi", "39.90", "M"), ("Blusa cropped canelada", "19.90", "P"),
               ("Calça jeans cintura alta", "49.90", "38"), ("Short jeans destroyed", "29.90", "40"),
               ("Camiseta básica branca", "15.00", "G")],
    "Calçados": [("Sandália rasteira dourada", "24.90", "36"), ("Tênis branco casual", "59.90", "37"),
                 ("Chinelo slide rosa", "14.90", "35/36"), ("Sapatilha preta", "22.00", "38")],
    "Bijuterias": [("Colar de pérolas", "12.90", ""), ("Brinco argola grande", "9.90", ""),
                   ("Pulseira de miçangas", "7.50", ""), ("Anel ajustável coração", "6.00", "")],
    "Bolsas e acessórios": [("Bolsa transversal caramelo", "34.90", ""), ("Óculos de sol gatinho", "18.00", ""),
                            ("Presilha de cabelo kit", "8.00", "")],
    "Casa e variedades": [("Kit potes de vidro", "27.00", ""), ("Pano de prato bordado", "10.00", ""),
                          ("Caneca personalizada", "16.00", "")],
    "Infantil": [("Conjunto infantil algodão", "21.00", "4"), ("Sandália infantil", "17.00", "26")],
}
BUSCAS = ["vestido", "sandalia", "tenis", "bolsa", "colar", "brinco", "short", "calça jeans", "blusa",
          "oculos", "infantil", "biquini", "perfume", "maquiagem", "relogio", "sapatilha", "caneca"]
NOMES = ["Maria Silva", "Ana Souza", "Joana Lima", "Carla Rocha", "Paula Alves", "Rita Gomes", "Lúcia Costa"]


class Command(BaseCommand):
    help = "Popula a loja com dados de demonstração"

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true", help="Apaga pedidos, buscas e produtos antes")

    def handle(self, *args, limpar=False, **opts):
        if limpar:
            Pedido.objects.all().delete()
            Busca.objects.all().delete()
            Produto.objects.all().delete()
            Categoria.objects.all().delete()

        produtos = []
        for ordem, (cat_nome, itens) in enumerate(CATALOGO.items()):
            cat, _ = Categoria.objects.get_or_create(nome=cat_nome, defaults={"ordem": ordem})
            for nome, preco, tam in itens:
                p, _ = Produto.objects.get_or_create(nome=nome, defaults={
                    "categoria": cat, "preco": Decimal(preco), "tamanho": tam,
                    "estoque": random.randint(1, 8), "destaque": random.random() < .3,
                    "condicao": random.choice(Produto.Condicao.values),
                    "descricao": "Peça selecionada com carinho pela Bruna. Confira as fotos e garanta o seu!",
                })
                produtos.append(p)

        agora = timezone.now()
        for _ in range(300):
            termo = random.choices(BUSCAS, weights=range(len(BUSCAS), 0, -1))[0]
            achados = Produto.objects.filter(nome__icontains=termo).count()
            b = Busca.objects.create(termo=termo, resultados=achados)
            Busca.objects.filter(pk=b.pk).update(criado_em=agora - timedelta(days=random.randint(0, 45),
                                                                             minutes=random.randint(0, 1440)))

        for p in produtos:
            Produto.objects.filter(pk=p.pk).update(visualizacoes=random.randint(5, 180))

        for _ in range(40):
            entrega = random.random() < .55
            escolhidos = random.sample(produtos, k=random.randint(1, 3))
            subtotal = sum(p.preco for p in escolhidos)
            taxa = Decimal("5.00") if entrega else Decimal(0)
            pedido = Pedido.objects.create(
                nome=random.choice(NOMES), email="cliente@exemplo.com", telefone="(93) 99999-0000",
                tipo_entrega="entrega" if entrega else "retirada",
                endereco="Rua Principal, 100" if entrega else "", bairro="Centro" if entrega else "",
                subtotal=subtotal, taxa_entrega=taxa, total=subtotal + taxa,
                status=random.choices(["pago", "entregue", "aguardando", "cancelado"], weights=[4, 4, 1, 1])[0],
                estoque_baixado=True,
            )
            ItemPedido.objects.bulk_create([ItemPedido(pedido=pedido, produto=p, nome_produto=p.nome, preco=p.preco)
                                            for p in escolhidos])
            Pedido.objects.filter(pk=pedido.pk).update(criado_em=agora - timedelta(days=random.randint(0, 45)))

        self.stdout.write(self.style.SUCCESS(f"Pronto: {len(produtos)} produtos, 300 buscas, 40 pedidos."))
