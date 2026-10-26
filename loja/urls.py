from django.urls import path

from . import views

app_name = "loja"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.buscar, name="buscar"),
    path("categoria/<slug:slug>/", views.categoria, name="categoria"),
    path("produto/<slug:slug>/", views.produto, name="produto"),
    path("sacola/", views.carrinho, name="carrinho"),
    path("sacola/adicionar/<int:produto_id>/", views.carrinho_adicionar, name="carrinho_adicionar"),
    path("sacola/atualizar/<int:produto_id>/", views.carrinho_atualizar, name="carrinho_atualizar"),
    path("sacola/remover/<int:produto_id>/", views.carrinho_remover, name="carrinho_remover"),
    path("finalizar/", views.checkout, name="checkout"),
    path("pedido/<uuid:codigo>/", views.pedido_detalhe, name="pedido"),
    path("pedido/<uuid:codigo>/pagar/", views.pagar, name="pagar"),
    path("pedido/<uuid:codigo>/retorno/", views.pagamento_retorno, name="pagamento_retorno"),
    path("mercadopago/webhook/", views.mp_webhook, name="mp_webhook"),
]
