# Achadinhos da Bruna 🛍️♥

Loja online do bazar **Achadinhos da Bruna** — novos, seminovos e usados em Rurópolis-PA.
30% das vendas vão para a ONG.

- **Loja**: catálogo por categoria, busca, filtros (condição/preço), sacola, checkout
- **Entrega** em Rurópolis (taxa fixa) ou **retirada no local** (grátis)
- **Pagamento** via Mercado Pago Checkout Pro (Pix, cartão, boleto) com webhook
- **Painel** (`/painel/`, só para administradores): faturamento, valor para a ONG,
  mais/menos buscados, buscas sem resultado, mais/menos vendidos, mais visitados × conversão,
  receita por categoria, estoque baixo e últimos pedidos
- **Admin** (`/admin/`): cadastrar produtos com foto, gerenciar pedidos e status

## Rodando no computador

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # depois edite o .env
python manage.py migrate
python manage.py createsuperuser
python manage.py popular_demo   # opcional: dados de exemplo para ver o painel
python manage.py runserver
```

Abra http://127.0.0.1:8000 (loja), http://127.0.0.1:8000/admin (cadastro) e
http://127.0.0.1:8000/painel (dashboard).

Para apagar os dados de exemplo: `python manage.py popular_demo --limpar` apaga tudo e recria;
ou apague pelo admin.

## Mercado Pago

1. Crie uma aplicação em https://www.mercadopago.com.br/developers/panel/app
2. Copie o **Access Token de teste** (`TEST-...`) para `MERCADOPAGO_ACCESS_TOKEN` no `.env`
3. Teste compras com os [cartões de teste](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-content/your-integrations/test/cards)
4. Em produção, troque pelo Access Token de produção (`APP_USR-...`)

**Webhook:** o Mercado Pago precisa alcançar o site pela internet. Em produção, configure
`SITE_URL=https://seu-dominio` e, no painel do MP (Suas integrações → Webhooks), cadastre
`https://seu-dominio/mercadopago/webhook/` com o evento **Pagamentos**. Copie a assinatura
secreta para `MERCADOPAGO_WEBHOOK_SECRET`.
Para testar localmente com webhook, use um túnel (ex.: `ngrok http 8000`) e coloque a URL dele em `SITE_URL`.

O status do pedido nunca é confiado à URL de retorno: o site sempre consulta o pagamento na API
do Mercado Pago. Quando aprovado, o pedido vira **Pago** e o estoque é baixado (uma única vez).

## Fluxo do pedido

Aguardando pagamento → Pago → Em preparação → Pronto p/ retirada / Saiu para entrega → Entregue.
Mude o status em `/admin/loja/pedido/`. O cliente acompanha pelo link do pedido.

## Publicando (produção)

- `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` longa e aleatória, `DJANGO_ALLOWED_HOSTS` e
  `DJANGO_CSRF_TRUSTED_ORIGINS` com o domínio
- `python manage.py collectstatic` e sirva `staticfiles/` e `media/` pelo servidor web
  (Nginx) ou use um serviço como PythonAnywhere/Railway/Render
- HTTPS é obrigatório para o retorno automático do Mercado Pago
