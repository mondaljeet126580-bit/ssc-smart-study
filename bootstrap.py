from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from advanced_tools import register_advanced_tools
from market_diagnostics import register_market_diagnostics
import chart_bridge
from server import BearerTokenMiddleware, client, mcp

register_advanced_tools(mcp, client)
register_market_diagnostics(mcp, client)

# Keep MCP at the standard public /mcp endpoint. The MCP SDK's
# streamable_http_app already contains the /mcp route; mounting that app under
# another /mcp prefix would incorrectly create /mcp/mcp and causes 404s.
mcp_app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@asynccontextmanager
async def lifespan(_app):
    # A mounted MCP app does not automatically receive the child app's
    # lifespan. Start the session manager from the top-level application.
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)

# The bridge must be registered before the catch-all MCP mount.
app.mount("/chart-bridge", chart_bridge.app)

# The SDK app already exposes /mcp. Mount it at the application root so the
# public endpoint remains exactly https://<host>/mcp.
app.mount("/", mcp_app)
app.add_middleware(BearerTokenMiddleware)
