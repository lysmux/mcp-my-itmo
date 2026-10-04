from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.dormitory import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_dormitory() -> dict:
        """Dormitory settlement status (queue place, assigned building and address, check-in time). status is null without a settlement."""
        status = await api.get_status(client)
        return {"status": None if status is None else status.model_dump()}

    @app.tool()
    @tool_errors
    async def get_dormitory_payments() -> list[dict]:
        """Dormitory accommodation contracts and payment schedules per period; sum minus paid is still due."""
        periods = await api.get_payments(client)
        return [period.model_dump() for period in periods]
