from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from advanced_tools import register_advanced_tools
from market_diagnostics import register_market_diagnostics
from chart_bridge import router as chart_bridge_router
from server import BearerTokenMiddleware, client, mcp

# Register extra market/funding/chart tools before constructing the HTTP app.
register_advanced_tools(mcp, client)
register_market_diagnostics(mcp, client)

app = FastAPI()
app.mount("/mcp", mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
))
app.include_router(chart_bridge_router, prefix="/chart-bridge")
app.add_middleware(BearerTokenMiddleware)
