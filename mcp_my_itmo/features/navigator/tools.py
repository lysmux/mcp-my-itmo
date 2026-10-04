from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.navigator import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def navigator_search(query: str = "") -> list[dict]:
        """Campus buildings with an indoor map, filtered by name substring (empty query lists all)."""
        buildings = await api.search_buildings(client, query)
        return [building.model_dump() for building in buildings]
