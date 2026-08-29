from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from advanced_tools import register_advanced_tools
from market_diagnostics import register_market_diagnostics
import chart_bridge
from server import BearerTokenMiddleware, client, mcp

register_advanced_tools(mcp, client)
register_market_diagnostics(mcp, client)

mcp_app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

app = FastAPI()

# Expose both spellings. Some MCP clients normalize the configured URL to
# `/mcp/`, while others keep `/mcp`. Mounting both avoids a trailing-slash
# 404 without relying on an HTTP redirect that may be mishandled for POST.
app.mount("/mcp/", mcp_app)
app.mount("/mcp", mcp_app)
app.mount("/chart-bridge", chart_bridge.app)
app.add_middleware(BearerTokenMiddleware)
