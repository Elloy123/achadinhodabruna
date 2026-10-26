from django.conf import settings

from .carrinho import Carrinho
from .models import Categoria


def loja(request):
    return {
        "categorias_menu": Categoria.objects.all(),
        "qtd_carrinho": len(Carrinho(request)),
        "whatsapp_loja": settings.WHATSAPP_LOJA,
        "cidade_entrega": settings.CIDADE_ENTREGA,
    }
