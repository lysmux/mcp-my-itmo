from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.navigator.models import NavigatorBuilding

# Route per go-itmo (myitmo/navigator.go), live-verify pending.
# The response has no envelope and there is no server-side search, so the query filters by name.


async def search_buildings(client: MyItmoClient, query: str) -> list[NavigatorBuilding]:
    raw = await client.get("/navigator/buildings")
    buildings = [NavigatorBuilding.model_validate(item) for item in raw or []]
    needle = query.strip().casefold()
    return [b for b in buildings if needle in (b.name or "").casefold()]
