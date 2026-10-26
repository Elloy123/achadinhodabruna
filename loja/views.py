import hashlib
import hmac
import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import mercadopago_service as mp
from .carrinho import Carrinho
from .forms import CheckoutForm
from .models import Busca, Categoria, ItemPedido, Pedido, Produto

logger = logging.getLogger(__name__)
POR_PAGINA = 12


def _listar(request, produtos, contexto):
    ordem = request.GET.get("ordem", "")
    ordens = {"menor": "preco", "maior": "-preco", "novos": "-criado_em"}
    produtos = produtos.order_by(ordens.get(ordem, "-destaque"), "-criado_em")
    condicao = request.GET.get("condicao", "")
    if condicao in Produto.Condicao.values:
        produtos = produtos.filter(condicao=condicao)
    pagina = Paginator(produtos, POR_PAGINA).get_page(request.GET.get("page"))
    contexto.update({"pagina": pagina, "ordem": ordem, "condicao": condicao,
                     "condicoes": Produto.Condicao.choices})
    return render(request, "loja/lista.html", contexto)


def home(request):
    ativos = Produto.objects.filter(ativo=True, estoque__gt=0).select_related("categoria")
    return render(request, "loja/home.html", {
        "destaques": ativos.filter(destaque=True)[:8],
        "novidades": ativos[:8],
    })


def categoria(request, slug):
    cat = get_object_or_404(Categoria, slug=slug)
    produtos = Produto.objects.filter(ativo=True, estoque__gt=0, categoria=cat).select_related("categoria")
    return _listar(request, produtos, {"titulo": cat.nome, "categoria_atual": cat})


def buscar(request):
    termo = " ".join(request.GET.get("q", "").split())[:120]
    produtos = Produto.objects.filter(ativo=True, estoque__gt=0).select_related("categoria")
    if termo:
        produtos = produtos.filter(
            Q(nome__icontains=termo) | Q(descricao__icontains=termo) | Q(categoria__nome__icontains=termo)
        )
        # Registra só a primeira página para não contar a mesma busca várias vezes.
        if not request.GET.get("page"):
            Busca.objects.create(termo=termo.lower(), resultados=produtos.count())
    return _listar(request, produtos, {"titulo": f"Busca: “{termo}”" if termo else "Todos os achadinhos", "termo": termo})


def produto(request, slug):
    p = get_object_or_404(Produto.objects.select_related("categoria"), slug=slug, ativo=True)
    Produto.objects.filter(pk=p.pk).update(visualizacoes=F("visualizacoes") + 1)
    relacionados = (Produto.objects.filter(categoria=p.categoria, ativo=True, estoque__gt=0)
                    .exclude(pk=p.pk)[:4])
    return render(request, "loja/produto.html", {"produto": p, "relacionados": relacionados})


# ---------- Carrinho ----------

def carrinho(request):
    c = Carrinho(request)
    return render(request, "loja/carrinho.html", {"itens": list(c.itens()), "subtotal": c.subtotal,
                                                  "taxa_entrega": settings.TAXA_ENTREGA})


@require_POST
def carrinho_adicionar(request, produto_id):
    p = get_object_or_404(Produto, pk=produto_id, ativo=True)
    try:
        qtd = max(1, int(request.POST.get("quantidade", 1)))
    except ValueError:
        qtd = 1
    if p.estoque <= 0:
        messages.error(request, "Esse achadinho acabou de esgotar 😢")
    else:
        Carrinho(request).adicionar(p, qtd)
        messages.success(request, f"“{p.nome}” foi para a sacola!")
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = "loja:carrinho"
    return redirect(destino)


@require_POST
def carrinho_atualizar(request, produto_id):
    p = get_object_or_404(Produto, pk=produto_id)
    try:
        qtd = int(request.POST.get("quantidade", 0))
    except ValueError:
        qtd = 0
    Carrinho(request).definir(p, qtd)
    return redirect("loja:carrinho")


@require_POST
def carrinho_remover(request, produto_id):
    Carrinho(request).remover(produto_id)
    return redirect("loja:carrinho")


# ---------- Checkout e pagamento ----------

def checkout(request):
    c = Carrinho(request)
    itens = list(c.itens())
    if not itens:
        messages.info(request, "Sua sacola está vazia.")
        return redirect("loja:home")

    form = CheckoutForm(request.POST or None, initial={"tipo_entrega": Pedido.TipoEntrega.RETIRADA})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            pedido = form.save(commit=False)
            if pedido.tipo_entrega == Pedido.TipoEntrega.RETIRADA:
                pedido.endereco = pedido.bairro = pedido.referencia = ""
                pedido.taxa_entrega = 0
            else:
                pedido.taxa_entrega = settings.TAXA_ENTREGA
            pedido.subtotal = sum(i["total"] for i in itens)
            pedido.total = pedido.subtotal + pedido.taxa_entrega
            pedido.save()
            ItemPedido.objects.bulk_create([
                ItemPedido(pedido=pedido, produto=i["produto"], nome_produto=i["produto"].nome,
                           preco=i["produto"].preco, quantidade=i["quantidade"])
                for i in itens
            ])
        c.limpar()
        return redirect("loja:pagar", codigo=pedido.codigo)

    return render(request, "loja/checkout.html", {
        "form": form, "itens": itens, "subtotal": c.subtotal,
        "taxa_entrega": settings.TAXA_ENTREGA, "endereco_retirada": settings.ENDERECO_RETIRADA,
    })


def pagar(request, codigo):
    pedido = get_object_or_404(Pedido, codigo=codigo)
    if pedido.status != Pedido.Status.AGUARDANDO:
        return redirect(pedido)
    try:
        pref_id, link = mp.criar_preferencia(pedido)
    except mp.MercadoPagoNaoConfigurado:
        messages.warning(request, "Pagamento online ainda não configurado. Fale com a gente pelo WhatsApp para finalizar.")
        return redirect(pedido)
    except Exception:
        logger.exception("Falha ao criar preferência do pedido %s", pedido.pk)
        messages.error(request, "Não conseguimos abrir o pagamento agora. Tente novamente em instantes.")
        return redirect(pedido)
    pedido.mp_preference_id = pref_id
    pedido.save(update_fields=["mp_preference_id"])
    return redirect(link)


def pagamento_retorno(request, codigo):
    """Volta do Mercado Pago. Confere o pagamento direto na API (não confia na URL)."""
    pedido = get_object_or_404(Pedido, codigo=codigo)
    payment_id = request.GET.get("payment_id") or request.GET.get("collection_id")
    if payment_id and payment_id != "null":
        try:
            pagamento = mp.consultar_pagamento(payment_id)
        except mp.MercadoPagoNaoConfigurado:
            pagamento = None
        if pagamento and str(pagamento.get("external_reference")) == str(pedido.pk):
            mp.aplicar_pagamento(pedido, pagamento)
    return redirect(pedido)


def pedido_detalhe(request, codigo):
    pedido = get_object_or_404(Pedido.objects.prefetch_related("itens"), codigo=codigo)
    return render(request, "loja/pedido.html", {"pedido": pedido,
                                                "endereco_retirada": settings.ENDERECO_RETIRADA})


def _assinatura_valida(request, data_id):
    """Valida o cabeçalho x-signature do webhook, se houver segredo configurado."""
    segredo = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")
    if not segredo:
        return True
    partes = dict(p.split("=", 1) for p in request.headers.get("x-signature", "").split(",") if "=" in p)
    ts, v1 = partes.get("ts", "").strip(), partes.get("v1", "").strip()
    if not ts or not v1:
        return False
    manifesto = f"id:{str(data_id).lower()};request-id:{request.headers.get('x-request-id', '')};ts:{ts};"
    esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


@csrf_exempt
@require_POST
def mp_webhook(request):
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        corpo = {}
    tipo = request.GET.get("type") or request.GET.get("topic") or corpo.get("type")
    data_id = request.GET.get("data.id") or request.GET.get("id") or corpo.get("data", {}).get("id")
    if tipo != "payment" or not data_id:
        return HttpResponse(status=200)
    if not _assinatura_valida(request, data_id):
        return HttpResponseBadRequest("assinatura inválida")

    pagamento = mp.consultar_pagamento(data_id)
    if pagamento:
        pedido = Pedido.objects.filter(pk=pagamento.get("external_reference") or 0).first()
        if pedido:
            mp.aplicar_pagamento(pedido, pagamento)
    return HttpResponse(status=200)
