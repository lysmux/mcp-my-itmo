from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.personalities.models import Person, PersonSummary

# Endpoints per go-itmo (myitmo/personalities.go); live-verify pending.
# Search responds with {"result": {"count": N, "data": [...]}}; a person card is {"result": {...}}.

DEFAULT_LIMIT = 20


async def search_people(
    client: MyItmoClient, query: str, limit: int = DEFAULT_LIMIT
) -> list[PersonSummary]:
    text = query.strip()
    if not text:
        raise ToolError("Search query must not be empty.")
    envelope = await client.get(
        "/personalities/persons", params={"q": text, "limit": max(limit, 1), "offset": 0}
    )
    page = envelope.get("result") or {}
    return [PersonSummary.model_validate(raw) for raw in page.get("data") or []]


async def get_person(client: MyItmoClient, person_id: int) -> Person:
    response = await client.request("GET", client.api_url(f"/personalities/persons/{person_id}"))
    if response.status_code == 404:
        raise ToolError(f"Person {person_id} not found")
    response.raise_for_status()
    card = response.json().get("result")
    if not card:
        raise ToolError(f"Person {person_id} not found")
    return Person.model_validate(card)
