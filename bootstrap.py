from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from advanced_tools import register_advanced_tools
from market_diagnostics import register_market_diagnostics
import chart_bridge
from server import BearerTokenMiddleware, client, mcp

register_advanced_tools(mcp, client)
register_market_diagnostics(mcp, client)

# The MCP SDK's streamable_http_app exposes its own /mcp route. Mounting it at
# the application root keeps the public endpoint exactly /mcp instead of
# accidentally creating /mcp/mcp.
mcp_app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/chart-bridge", chart_bridge.app)
app.mount("/", mcp_app)
app.add_middleware(BearerTokenMiddleware)
