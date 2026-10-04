from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.election import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def list_election_offers(kind: str = "election") -> list[dict]:
        """Courses open for election. kind: 'election' (elective disciplines; each has per-semester group_flow), 'intro' (introductory courses) or 'facultative' (optional courses). For intro/facultative the result is a nested tree; the ids on flow-level nodes (those with work_type) are what choose_election takes."""
        offers = await api.list_election_offers(client, kind)
        return [offer.model_dump(exclude_none=True) for offer in offers]

    @app.tool()
    @tool_errors
    async def get_my_elections() -> dict:
        """Own election state for all three flows (election, intro, facultative): open window/period, chosen flows, status (intro/facultative: 0 none, 1 booked but unconfirmed, 2 confirmed) and timetable clashes. A section the student cannot access reports only an error."""
        return await api.get_my_elections(client)

    @app.tool()
    @tool_errors
    async def choose_election(offer_id: int, kind: str = "facultative") -> dict:
        """BOOKS A REAL COURSE FLOW (kind 'intro' or 'facultative' only). Before calling, you MUST show the user the exact course/flow (name, teacher, kind; see list_election_offers) and get an explicit yes; never choose speculatively. offer_id is a flow id. The booking stays unconfirmed (it can expire) until confirm_election. Result echoes the booked offer_id and kind."""
        await api.choose_flow(client, kind, offer_id)
        return {"booked": True, "kind": kind, "offer_id": offer_id, "confirmed": False}

    @app.tool()
    @tool_errors
    async def confirm_election(kind: str = "facultative") -> dict:
        """CONFIRMS THE CURRENT BOOKING for 'intro' or 'facultative'. Before calling, you MUST show the user all currently chosen flows (get_my_elections) and get an explicit yes. The server refuses while required groups are unsatisfied or clashes exist."""
        await api.confirm_choice(client, kind)
        return {"confirmed": True, "kind": kind}

    @app.tool()
    @tool_errors
    async def withdraw_election(choice_id: int, kind: str = "facultative") -> dict:
        """RELEASES A REAL BOOKED COURSE FLOW (kind 'intro' or 'facultative'). Before calling, you MUST show the user the exact chosen course/flow (see get_my_elections) and get an explicit yes. choice_id is the flow id. Result echoes the withdrawn choice_id and kind."""
        await api.withdraw_flow(client, kind, choice_id)
        return {"withdrawn": True, "kind": kind, "choice_id": choice_id}
