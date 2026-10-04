from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.practices import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_my_practices() -> list[dict]:
        """My internships grouped by study year: dates, supervisor, mark and badge colour."""
        years = await api.get_practices(client)
        return [year.model_dump() for year in years]

    @app.tool()
    @tool_errors
    async def get_practice(practice_id: int) -> dict:
        """One practice: place, curator, supervisors, progress step (status_order 1-7) and individual assignment."""
        practice = await api.get_practice(client, practice_id)
        return practice.model_dump()
