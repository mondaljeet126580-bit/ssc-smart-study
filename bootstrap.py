from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from advanced_tools import register_advanced_tools
from server import BearerTokenMiddleware, client, mcp

# Register extra market/funding/chart tools before constructing the HTTP app.
register_advanced_tools(mcp, client)

app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
app.add_middleware(BearerTokenMiddleware)
