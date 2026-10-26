from django.contrib import admin
from django.utils.html import format_html

from .models import Busca, Categoria, ItemPedido, Pedido, Produto

admin.site.site_header = "Achadinhos da Bruna — Administração"
admin.site.site_title = "Achadinhos da Bruna"
admin.site.index_title = "Gerenciar loja"


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nome", "ordem"]
    list_editable = ["ordem"]
    prepopulated_fields = {"slug": ["nome"]}


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ["miniatura", "nome", "categoria", "condicao", "preco", "estoque", "destaque", "ativo", "visualizacoes"]
    list_display_links = ["miniatura", "nome"]
    list_editable = ["preco", "estoque", "destaque", "ativo"]
    list_filter = ["categoria", "condicao", "ativo", "destaque"]
    search_fields = ["nome", "descricao"]
    prepopulated_fields = {"slug": ["nome"]}

    @admin.display(description="")
    def miniatura(self, obj):
        if obj.imagem:
            return format_html('<img src="{}" style="height:40px;border-radius:6px">', obj.imagem.url)
        return "—"


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    readonly_fields = ["produto", "nome_produto", "preco", "quantidade"]
    can_delete = False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ["id", "nome", "telefone", "tipo_entrega", "total", "status", "mp_status", "criado_em"]
    list_editable = ["status"]
    list_filter = ["status", "tipo_entrega", "criado_em"]
    search_fields = ["nome", "email", "telefone", "mp_payment_id"]
    readonly_fields = ["codigo", "subtotal", "taxa_entrega", "total", "mp_preference_id", "mp_payment_id",
                       "mp_status", "criado_em", "atualizado_em"]
    inlines = [ItemPedidoInline]


@admin.register(Busca)
class BuscaAdmin(admin.ModelAdmin):
    list_display = ["termo", "resultados", "criado_em"]
    search_fields = ["termo"]
    list_filter = ["criado_em"]
