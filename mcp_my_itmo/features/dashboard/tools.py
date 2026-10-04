from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.dashboard import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_dashboard() -> list[dict]:
        """Home-page widget layout of the cabinet (widget names and grid positions)."""
        widgets = await api.get_dashboard(client)
        return [widget.model_dump() for widget in widgets]

    @app.tool()
    @tool_errors
    async def get_menu() -> list[dict]:
        """Sidebar navigation menu of the cabinet; titles are translation keys."""
        items = await api.get_menu(client)
        return [item.model_dump() for item in items]
