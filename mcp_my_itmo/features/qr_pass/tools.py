from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.qr_pass import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_qr_pass() -> dict:
        """Digital building pass: qr_hex is the exact text to encode as a QR code (byte mode, level L)."""
        return (await api.get_pass(client)).model_dump()
