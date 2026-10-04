from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.checklist import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_checkout_status() -> dict:
        """Clearance (bypass) sheet: personal and per-department debts; decision_id 1 problem, 2 warning, 3 cleared."""
        return (await api.get_bypass(client)).model_dump()
