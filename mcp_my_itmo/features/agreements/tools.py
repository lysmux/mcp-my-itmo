from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.agreements import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def list_agreements() -> list[dict]:
        """Agreements and consents (e.g. personal-data processing) with their version history. Each version has a status (status_id 6 signed, 11 signing in progress, 8 rejected, 9 revoked; status_name is the readable label); the newest version by date is the current one. Use the agreement id with accept_agreement."""
        agreements = await api.list_agreements(client)
        return [agreement.model_dump(exclude_none=True) for agreement in agreements]

    @app.tool()
    @tool_errors
    async def accept_agreement(agreement_id: str) -> dict:
        """ACCEPTS A REAL LEGAL AGREEMENT on the student's behalf (starts signing the latest version). Before calling, you MUST show the user the exact agreement (id and title from list_agreements) and get an explicit yes; never accept speculatively or in bulk. Result echoes the agreement_id and the created sign task ids. Endpoint is assumed from go-itmo and not yet verified live; the signing may need a further confirmation step in my.itmo.ru."""
        task = await api.accept_agreement(client, agreement_id)
        return {"agreement_id": agreement_id, "accepted": True, **task.model_dump(exclude_none=True)}
