from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from delta_client import DeltaAPIError, client

mcp = MCPServer(
    "Jeet Delta Exchange MCP",
    title="Jeet Delta Exchange MCP",
    description=(
        "Remote MCP server for Delta Exchange India. Provides public market data, "
        "read-only account data, and explicitly gated trading tools."
    ),
    version="1.0.0",
)


def _live_trading_enabled() -> bool:
    return os.getenv("ENABLE_LIVE_TRADING", "false").lower() in {"1", "true", "yes", "on"}


def _require_account_access() -> None:
    if not client.has_credentials:
        raise RuntimeError(
            "Delta account access is not configured. Set DELTA_API_KEY and DELTA_API_SECRET in server secrets."
        )


def _clean_params(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None and v != ""}


@mcp.tool()
async def get_products(page_size: int = 50, after: str | None = None) -> Any:
    """Get available Delta Exchange trading products."""
    page_size = max(1, min(page_size, 100))
    return await client.public("GET", "/v2/products", _clean_params(page_size=page_size, after=after))


@mcp.tool()
async def get_product(symbol: str) -> Any:
    """Get product details for a symbol such as BTCUSD or ETHUSD."""
    return await client.public("GET", f"/v2/products/{symbol.upper()}")


@mcp.tool()
async def get_ticker(symbol: str) -> Any:
    """Get the live ticker for one Delta Exchange product."""
    return await client.public("GET", f"/v2/tickers/{symbol.upper()}")


@mcp.tool()
async def get_tickers(contract_types: str | None = None) -> Any:
    """Get live tickers, optionally filtered by comma-separated contract types."""
    return await client.public("GET", "/v2/tickers", _clean_params(contract_types=contract_types))


@mcp.tool()
async def get_orderbook(symbol: str, depth: int = 20) -> Any:
    """Get the public L2 order book for a product symbol."""
    depth = max(1, min(depth, 1000))
    return await client.public("GET", f"/v2/l2orderbook/{symbol.upper()}", {"depth": depth})


@mcp.tool()
async def get_candles(
    symbol: str,
    resolution: str = "5m",
    start: int | None = None,
    end: int | None = None,
) -> Any:
    """Get OHLC candles. Start/end are Unix timestamps in seconds when supported by Delta."""
    params = _clean_params(symbol=symbol.upper(), resolution=resolution, start=start, end=end)
    return await client.public("GET", "/v2/history/candles", params)


@mcp.tool()
async def get_public_trades(symbol: str, page_size: int = 50) -> Any:
    """Get recent public trades for a product symbol."""
    page_size = max(1, min(page_size, 1000))
    return await client.public("GET", f"/v2/trades/{symbol.upper()}", {"page_size": page_size})


@mcp.tool()
async def get_balance() -> Any:
    """Get authenticated wallet balances."""
    _require_account_access()
    return await client.private("GET", "/v2/wallet/balances")


@mcp.tool()
async def get_positions(product_id: int | None = None, underlying_asset_symbol: str | None = None) -> Any:
    """Get real-time positions. Provide product_id or an underlying asset symbol when needed."""
    _require_account_access()
    if product_id is not None and underlying_asset_symbol:
        raise ValueError("Provide either product_id or underlying_asset_symbol, not both.")
    if product_id is None and not underlying_asset_symbol:
        raise ValueError("Provide product_id or underlying_asset_symbol.")
    params = _clean_params(product_id=product_id, underlying_asset_symbol=underlying_asset_symbol)
    return await client.private("GET", "/v2/positions", params)


@mcp.tool()
async def get_all_positions(
    product_ids: str | None = None,
    contract_types: str | None = None,
) -> Any:
    """Get all open positions with margin-dependent fields."""
    _require_account_access()
    return await client.private(
        "GET",
        "/v2/positions/margined",
        _clean_params(product_ids=product_ids, contract_types=contract_types),
    )


@mcp.tool()
async def get_open_orders(
    product_id: int | None = None,
    state: str | None = "open",
    page_size: int = 50,
    after: str | None = None,
    before: str | None = None,
) -> Any:
    """Get open/pending orders and pagination metadata."""
    _require_account_access()
    page_size = max(1, min(page_size, 100))
    return await client.private(
        "GET",
        "/v2/orders",
        _clean_params(product_id=product_id, state=state, page_size=page_size, after=after, before=before),
    )


@mcp.tool()
async def get_order(order_id: int) -> Any:
    """Get one order by ID."""
    _require_account_access()
    return await client.private("GET", f"/v2/orders/{order_id}")


@mcp.tool()
async def get_order_history(
    product_ids: str | None = None,
    order_types: str | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    page_size: int = 50,
    after: str | None = None,
    before: str | None = None,
) -> Any:
    """Get closed/cancelled order history."""
    _require_account_access()
    page_size = max(1, min(page_size, 100))
    return await client.private(
        "GET",
        "/v2/orders/history",
        _clean_params(
            product_ids=product_ids,
            order_types=order_types,
            start_time=start_time,
            end_time=end_time,
            page_size=page_size,
            after=after,
            before=before,
        ),
    )


@mcp.tool()
async def get_fills(
    product_ids: str | None = None,
    contract_types: str | None = None,
    page_size: int = 50,
    after: str | None = None,
    before: str | None = None,
) -> Any:
    """Get fill/trade history."""
    _require_account_access()
    page_size = max(1, min(page_size, 100))
    return await client.private(
        "GET",
        "/v2/fills",
        _clean_params(
            product_ids=product_ids,
            contract_types=contract_types,
            page_size=page_size,
            after=after,
            before=before,
        ),
    )


@mcp.tool()
async def get_profile() -> Any:
    """Get the authenticated Delta Exchange profile."""
    _require_account_access()
    return await client.private("GET", "/v2/profile")


@mcp.tool()
async def get_order_leverage(product_id: int) -> Any:
    """Get the configured order leverage for a product."""
    _require_account_access()
    return await client.private("GET", f"/v2/products/{product_id}/orders/leverage")


@mcp.tool()
async def set_order_leverage(product_id: int, leverage: int, dry_run: bool = True) -> Any:
    """Set product order leverage. dry_run defaults to true."""
    _require_account_access()
    payload = {"leverage": leverage}
    if dry_run or not _live_trading_enabled():
        return {"dry_run": True, "would_send": {"method": "POST", "path": f"/v2/products/{product_id}/orders/leverage", "body": payload}}
    return await client.private("POST", f"/v2/products/{product_id}/orders/leverage", body=payload)


@mcp.tool()
async def place_order(
    product_id: int,
    size: int,
    side: str,
    order_type: str = "market_order",
    limit_price: str | None = None,
    stop_order_type: str | None = None,
    stop_price: str | None = None,
    time_in_force: str | None = None,
    post_only: bool = False,
    client_order_id: str | None = None,
    dry_run: bool = True,
) -> Any:
    """Create a Delta order. Dry-run is mandatory by default; live trading requires ENABLE_LIVE_TRADING=true and dry_run=false."""
    _require_account_access()
    side = side.lower().strip()
    order_type = order_type.lower().strip()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'.")
    if size <= 0:
        raise ValueError("size must be greater than 0.")
    if order_type in {"limit_order", "limit"} and not limit_price:
        raise ValueError("limit_price is required for limit orders.")
    payload = _clean_params(
        product_id=product_id,
        size=size,
        side=side,
        order_type=order_type,
        limit_price=limit_price,
        stop_order_type=stop_order_type,
        stop_price=stop_price,
        time_in_force=time_in_force,
        post_only=post_only,
        client_order_id=client_order_id,
    )
    if dry_run or not _live_trading_enabled():
        return {
            "dry_run": True,
            "live_trading_enabled": _live_trading_enabled(),
            "would_send": {"method": "POST", "path": "/v2/orders", "body": payload},
        }
    return await client.private("POST", "/v2/orders", body=payload)


@mcp.tool()
async def edit_order(
    order_id: int,
    limit_price: str | None = None,
    size: int | None = None,
    stop_price: str | None = None,
    trail_amount: str | None = None,
    post_only: bool | None = None,
    dry_run: bool = True,
) -> Any:
    """Edit an order. Dry-run is the default."""
    _require_account_access()
    payload = _clean_params(
        id=order_id,
        limit_price=limit_price,
        size=size,
        stop_price=stop_price,
        trail_amount=trail_amount,
        post_only=post_only,
    )
    if dry_run or not _live_trading_enabled():
        return {"dry_run": True, "would_send": {"method": "PUT", "path": "/v2/orders", "body": payload}}
    return await client.private("PUT", "/v2/orders", body=payload)


@mcp.tool()
async def cancel_order(order_id: int, dry_run: bool = True) -> Any:
    """Cancel an order. Dry-run is the default."""
    _require_account_access()
    payload = {"id": order_id}
    if dry_run or not _live_trading_enabled():
        return {"dry_run": True, "would_send": {"method": "DELETE", "path": "/v2/orders", "body": payload}}
    return await client.private("DELETE", "/v2/orders", body=payload)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Protect the public /mcp endpoint without ever storing MCP credentials in Git."""

    async def dispatch(self, request: Request, call_next):
        required = os.getenv("MCP_ACCESS_TOKEN", "").strip()
        if not required:
            return await call_next(request)
        if request.url.path == "/health":
            return JSONResponse({"ok": True})
        auth = request.headers.get("authorization", "")
        expected = f"Bearer {required}"
        if auth != expected:
            return JSONResponse({"error": "Unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)


app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
app.add_middleware(BearerTokenMiddleware)


async def health(request: Request):
    return JSONResponse(
        {
            "ok": True,
            "service": "Jeet Delta Exchange MCP",
            "delta_base_url": client.base_url,
            "account_credentials_configured": client.has_credentials,
            "live_trading_enabled": _live_trading_enabled(),
            "mcp_endpoint": "/mcp",
        }
    )


app.add_route("/health", health, methods=["GET"])
