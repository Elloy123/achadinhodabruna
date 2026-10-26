from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.shortcuts import render
from django.utils import timezone

from loja.models import Busca, ItemPedido, Pedido, Produto

STATUS_PAGOS = ["pago", "preparando", "pronto", "enviado", "entregue"]
PERIODOS = {"7": 7, "30": 30, "90": 90, "365": 365}


@staff_member_required
def dashboard(request):
    periodo = request.GET.get("periodo", "30")
    dias = PERIODOS.get(periodo)
    inicio = timezone.now() - timedelta(days=dias) if dias else None

    pedidos = Pedido.objects.filter(status__in=STATUS_PAGOS)
    buscas = Busca.objects.all()
    itens = ItemPedido.objects.filter(pedido__status__in=STATUS_PAGOS)
    if inicio:
        pedidos = pedidos.filter(criado_em__gte=inicio)
        buscas = buscas.filter(criado_em__gte=inicio)
        itens = itens.filter(pedido__criado_em__gte=inicio)

    # --- KPIs ---
    tot = pedidos.aggregate(fat=Coalesce(Sum("total"), Decimal(0)), sub=Coalesce(Sum("subtotal"), Decimal(0)),
                            n=Count("id"))
    total_buscas = buscas.count()
    sem_resultado = buscas.filter(resultados=0).count()
    kpis = {
        "faturamento": tot["fat"],
        "pedidos": tot["n"],
        "ticket": (tot["fat"] / tot["n"]) if tot["n"] else Decimal(0),
        "ong": (tot["sub"] * settings.PERCENTUAL_ONG).quantize(Decimal("0.01")),
        "buscas": total_buscas,
        "sem_resultado_pct": round(100 * sem_resultado / total_buscas) if total_buscas else 0,
        "aguardando": Pedido.objects.filter(status="aguardando").count(),
        "a_preparar": Pedido.objects.filter(status__in=["pago", "preparando"]).count(),
    }

    # --- Buscas ---
    por_termo = buscas.values("termo").annotate(qtd=Count("id")).order_by()
    mais_buscados = list(por_termo.order_by("-qtd", "termo")[:10])
    menos_buscados = list(por_termo.order_by("qtd", "termo")[:10])
    buscas_sem_resultado = list(buscas.filter(resultados=0).values("termo")
                                .annotate(qtd=Count("id")).order_by("-qtd", "termo")[:10])

    # --- Vendas por produto ---
    receita = ExpressionWrapper(F("preco") * F("quantidade"), output_field=DecimalField())
    por_produto = (itens.values("nome_produto").annotate(qtd=Sum("quantidade"), receita=Sum(receita)).order_by())
    mais_vendidos = list(por_produto.order_by("-qtd")[:10])

    filtro_vendas = Q(itens_vendidos__pedido__status__in=STATUS_PAGOS)
    if inicio:
        filtro_vendas &= Q(itens_vendidos__pedido__criado_em__gte=inicio)
    produtos_ativos = Produto.objects.filter(ativo=True).annotate(
        vendidos=Coalesce(Sum("itens_vendidos__quantidade", filter=filtro_vendas), 0))
    menos_vendidos = list(produtos_ativos.filter(estoque__gt=0).order_by("vendidos", "-visualizacoes")[:10])
    mais_vistos = list(produtos_ativos.order_by("-visualizacoes")[:10])
    for p in mais_vistos:
        p.conversao = round(100 * p.vendidos / p.visualizacoes, 1) if p.visualizacoes else 0
    estoque_baixo = Produto.objects.filter(ativo=True, estoque__lte=2).order_by("estoque", "nome")[:10]

    # --- Séries para gráficos ---
    vendas_dia = list(pedidos.annotate(dia=TruncDate("criado_em")).values("dia")
                      .annotate(total=Sum("total"), n=Count("id")).order_by("dia"))
    buscas_dia = list(buscas.annotate(dia=TruncDate("criado_em")).values("dia")
                      .annotate(n=Count("id")).order_by("dia"))
    por_categoria = list(itens.values("produto__categoria__nome")
                         .annotate(receita=Sum(receita)).order_by("-receita"))
    por_entrega = {r["tipo_entrega"]: r["n"] for r in pedidos.values("tipo_entrega").annotate(n=Count("id")).order_by()}

    graficos = {
        "vendas": {
            "labels": [v["dia"].strftime("%d/%m") for v in vendas_dia],
            "valores": [float(v["total"]) for v in vendas_dia],
            "pedidos": [v["n"] for v in vendas_dia],
        },
        "buscas": {
            "labels": [b["dia"].strftime("%d/%m") for b in buscas_dia],
            "valores": [b["n"] for b in buscas_dia],
        },
        "mais_buscados": {"labels": [b["termo"] for b in mais_buscados], "valores": [b["qtd"] for b in mais_buscados]},
        "mais_vendidos": {"labels": [v["nome_produto"] for v in mais_vendidos], "valores": [v["qtd"] for v in mais_vendidos]},
        "categorias": {
            "labels": [c["produto__categoria__nome"] or "Removido" for c in por_categoria],
            "valores": [float(c["receita"]) for c in por_categoria],
        },
        "entrega": {
            "labels": ["Entrega", "Retirada"],
            "valores": [por_entrega.get("entrega", 0), por_entrega.get("retirada", 0)],
        },
    }

    return render(request, "painel/dashboard.html", {
        "periodo": periodo,
        "periodos": [("7", "7 dias"), ("30", "30 dias"), ("90", "90 dias"), ("365", "1 ano"), ("tudo", "Tudo")],
        "kpis": kpis,
        "mais_buscados": mais_buscados,
        "menos_buscados": menos_buscados,
        "buscas_sem_resultado": buscas_sem_resultado,
        "mais_vendidos": mais_vendidos,
        "menos_vendidos": menos_vendidos,
        "mais_vistos": mais_vistos,
        "estoque_baixo": estoque_baixo,
        "ultimos_pedidos": Pedido.objects.order_by("-criado_em")[:8],
        "graficos": graficos,
    })
