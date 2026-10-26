import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Categoria(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name_plural = "categorias"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("loja:categoria", args=[self.slug])


class Produto(models.Model):
    class Condicao(models.TextChoices):
        NOVO = "novo", "Novo"
        SEMINOVO = "seminovo", "Seminovo"
        USADO = "usado", "Usado"

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="produtos")
    nome = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    preco_antigo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text="Opcional: aparece riscado como 'de/por'.")
    estoque = models.PositiveIntegerField(default=1)
    condicao = models.CharField(max_length=10, choices=Condicao.choices, default=Condicao.NOVO)
    tamanho = models.CharField(max_length=30, blank=True, help_text="Ex.: P, M, G, 38, Único")
    imagem = models.ImageField(upload_to="produtos/", blank=True)
    destaque = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    visualizacoes = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome)[:150] or "produto"
            slug, n = base, 2
            while Produto.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("loja:produto", args=[self.slug])

    @property
    def disponivel(self):
        return self.ativo and self.estoque > 0


class Busca(models.Model):
    """Registro de cada busca feita no site (alimenta o painel)."""
    termo = models.CharField(max_length=120, db_index=True)
    resultados = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.termo} ({self.resultados})"


class Pedido(models.Model):
    class Status(models.TextChoices):
        AGUARDANDO = "aguardando", "Aguardando pagamento"
        PAGO = "pago", "Pago"
        PREPARANDO = "preparando", "Em preparação"
        PRONTO = "pronto", "Pronto p/ retirada"
        ENVIADO = "enviado", "Saiu para entrega"
        ENTREGUE = "entregue", "Entregue"
        CANCELADO = "cancelado", "Cancelado"

    class TipoEntrega(models.TextChoices):
        ENTREGA = "entrega", "Entrega em Rurópolis"
        RETIRADA = "retirada", "Retirada no local"

    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nome = models.CharField(max_length=120)
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    tipo_entrega = models.CharField(max_length=10, choices=TipoEntrega.choices)
    endereco = models.CharField(max_length=200, blank=True)
    bairro = models.CharField(max_length=80, blank=True)
    referencia = models.CharField(max_length=150, blank=True)
    observacoes = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    taxa_entrega = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AGUARDANDO)
    mp_preference_id = models.CharField(max_length=100, blank=True)
    mp_payment_id = models.CharField(max_length=50, blank=True)
    mp_status = models.CharField(max_length=30, blank=True)
    estoque_baixado = models.BooleanField(default=False, editable=False)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pedido #{self.pk} — {self.nome}"

    def get_absolute_url(self):
        return reverse("loja:pedido", args=[self.codigo])

    @property
    def valor_ong(self):
        return (self.subtotal * settings.PERCENTUAL_ONG).quantize(Decimal("0.01"))

    def baixar_estoque(self):
        """Debita o estoque uma única vez, quando o pagamento é aprovado."""
        if self.estoque_baixado:
            return
        for item in self.itens.select_related("produto"):
            if item.produto:
                p = item.produto
                p.estoque = max(0, p.estoque - item.quantidade)
                p.save(update_fields=["estoque"])
        self.estoque_baixado = True
        self.save(update_fields=["estoque_baixado"])


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.SET_NULL, null=True, related_name="itens_vendidos")
    nome_produto = models.CharField(max_length=150)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantidade}x {self.nome_produto}"

    @property
    def total(self):
        return self.preco * self.quantidade
