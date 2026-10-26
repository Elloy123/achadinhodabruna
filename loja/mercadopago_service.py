"""Integração com o Mercado Pago (Checkout Pro)."""
import logging

import mercadopago
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class MercadoPagoNaoConfigurado(Exception):
    pass


def _sdk():
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        raise MercadoPagoNaoConfigurado("Defina MERCADOPAGO_ACCESS_TOKEN no arquivo .env")
    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def criar_preferencia(pedido):
    """Cria a preferência de pagamento e devolve (preference_id, init_point)."""
    itens = [
        {
            "id": str(item.produto_id or ""),
            "title": item.nome_produto[:250],
            "quantity": item.quantidade,
            "unit_price": float(item.preco),
            "currency_id": "BRL",
        }
        for item in pedido.itens.all()
    ]
    if pedido.taxa_entrega > 0:
        itens.append({
            "id": "entrega",
            "title": f"Taxa de entrega — {settings.CIDADE_ENTREGA}/{settings.UF_ENTREGA}",
            "quantity": 1,
            "unit_price": float(pedido.taxa_entrega),
            "currency_id": "BRL",
        })

    base = settings.SITE_URL
    retorno = base + reverse("loja:pagamento_retorno", args=[pedido.codigo])
    dados = {
        "items": itens,
        "payer": {"name": pedido.nome, "email": pedido.email},
        "external_reference": str(pedido.pk),
        "statement_descriptor": "ACHADINHOSBRUNA",
        "back_urls": {"success": retorno, "pending": retorno, "failure": retorno},
        "notification_url": base + reverse("loja:mp_webhook"),
    }
    # O MP só aceita auto_return com URLs públicas (https); em localhost é ignorado.
    if base.startswith("https://"):
        dados["auto_return"] = "approved"

    resposta = _sdk().preference().create(dados)
    corpo = resposta.get("response", {})
    if resposta.get("status") not in (200, 201):
        logger.error("Erro ao criar preferência MP: %s", corpo)
        raise RuntimeError(corpo.get("message", "Falha ao criar pagamento"))

    usa_sandbox = settings.MERCADOPAGO_ACCESS_TOKEN.startswith("TEST-")
    link = corpo.get("sandbox_init_point") if usa_sandbox else corpo.get("init_point")
    return corpo["id"], link


def consultar_pagamento(payment_id):
    resposta = _sdk().payment().get(payment_id)
    if resposta.get("status") != 200:
        return None
    return resposta["response"]


STATUS_MP_PARA_PEDIDO = {
    "approved": "pago",
    "authorized": "pago",
    "cancelled": "cancelado",
    "rejected": "cancelado",
    "refunded": "cancelado",
    "charged_back": "cancelado",
}


def aplicar_pagamento(pedido, pagamento):
    """Atualiza o pedido a partir dos dados de um pagamento consultado na API."""
    mp_status = pagamento.get("status", "")
    pedido.mp_payment_id = str(pagamento.get("id", ""))
    pedido.mp_status = mp_status
    novo = STATUS_MP_PARA_PEDIDO.get(mp_status)
    # Não rebaixa um pedido que já avançou no fluxo (preparando, enviado...).
    if novo and pedido.status in (pedido.Status.AGUARDANDO, pedido.Status.PAGO):
        pedido.status = novo
    pedido.save(update_fields=["mp_payment_id", "mp_status", "status", "atualizado_em"])
    if novo == "pago":
        pedido.baixar_estoque()
