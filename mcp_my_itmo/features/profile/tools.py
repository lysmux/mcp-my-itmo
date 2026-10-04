from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.profile import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_profile() -> dict:
        """Own personal data (name, ISU number, emails, groups) from the ITMO identity provider."""
        profile = await api.get_profile(client)
        return profile.model_dump(exclude_none=True)
