# Jeet Delta Exchange MCP

A standalone remote MCP server for **Delta Exchange India**. This project does **not** depend on Delta Exchange's official MCP repository; it talks directly to Delta's REST API and exposes the API through MCP Streamable HTTP.

## What it provides

Public market tools:
- `get_products`
- `get_product`
- `get_ticker`
- `get_tickers`
- `get_orderbook`
- `get_candles`
- `get_public_trades`

Account tools (API key + secret required):
- `get_balance`
- `get_positions`
- `get_all_positions`
- `get_open_orders`
- `get_order`
- `get_order_history`
- `get_fills`
- `get_profile`
- `get_order_leverage`

Trading tools (read-only/dry-run by default):
- `place_order`
- `edit_order`
- `cancel_order`
- `set_order_leverage`

## Security model

- **Never** commit a real Delta API key/secret to GitHub.
- Put Delta credentials in your cloud provider's secret/environment-variable store.
- `MCP_ACCESS_TOKEN` protects the remote `/mcp` endpoint. Give the MCP client the same Bearer token when your client supports bearer-token authentication.
- `ENABLE_LIVE_TRADING=false` is the default.
- Trading tools default to `dry_run=true`.
- To send real orders you must explicitly set `ENABLE_LIVE_TRADING=true`, use an API key with Delta trading permission, and call a trading tool with `dry_run=false`.
- Test on Delta's demo/testnet environment before live trading by setting `DELTA_BASE_URL=https://cdn-ind.testnet.deltaex.org` and using testnet credentials.

## Local run

Python 3.10+ is required by the current MCP Python SDK.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Set environment variables in your shell, or use a local .env loader of your choice.
export MCP_ACCESS_TOKEN='replace-with-a-long-random-token'
export DELTA_API_KEY='replace-me'
export DELTA_API_SECRET='replace-me'

uvicorn server:app --host 0.0.0.0 --port 8000
```

MCP endpoint:

```text
http://localhost:8000/mcp
```

Health endpoint:

```text
http://localhost:8000/health
```

## Docker

```bash
docker build -t jeet-delta-mcp .
docker run --rm -p 8000:8000 \
  -e MCP_ACCESS_TOKEN='replace-with-a-long-random-token' \
  -e DELTA_API_KEY='replace-me' \
  -e DELTA_API_SECRET='replace-me' \
  jeet-delta-mcp
```

## Cloud deployment

Deploy the repository as a normal Python/ASGI web service using the Dockerfile or the start command:

```text
uvicorn server:app --host 0.0.0.0 --port $PORT
```

The final MCP URL will normally be:

```text
https://YOUR-SERVICE-DOMAIN/mcp
```

The SDK uses Streamable HTTP for production MCP deployments. A reverse proxy/cloud platform should terminate HTTPS. The server disables the SDK's localhost-only DNS-rebinding check because the app is intended to run behind a real cloud hostname; keep the `MCP_ACCESS_TOKEN` enabled on public deployments.

## Delta API signing

Authenticated requests use Delta's documented HMAC-SHA256 signing scheme: HTTP method + timestamp + request path + query string + exact request body. The timestamp must be current because Delta accepts signatures only within a short time window. The implementation also sends the required `User-Agent` header.

## Current API base URLs

Production:

```text
https://api.india.delta.exchange
```

Demo/testnet:

```text
https://cdn-ind.testnet.deltaex.org
```

## Important

This server is an API bridge, not an autonomous trading strategy. It will not monitor the market by itself. A separate continuously running strategy/bot is needed for 24/7 automated trading.
