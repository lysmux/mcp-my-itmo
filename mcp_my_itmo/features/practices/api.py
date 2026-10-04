from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import unwrap_result
from mcp_my_itmo.features.practices.models import PracticeDetails, PracticeTask, PracticeYear

# Read endpoints per go-itmo (myitmo/practices.go); live-verify pending.
# Application, assignment-editing and report-upload routes are mutating and not exposed.


async def get_practices(client: MyItmoClient) -> list[PracticeYear]:
    envelope = await client.get("/practices/practices/all")
    return [PracticeYear.model_validate(raw) for raw in unwrap_result(envelope)]


async def get_practice(client: MyItmoClient, practice_id: int) -> PracticeDetails:
    response = await client.request(
        "GET", client.api_url("/practices/practices"), params={"id": practice_id}
    )
    if response.status_code == 404:
        raise _not_found(practice_id)
    response.raise_for_status()
    card = response.json().get("result")
    if not card:
        raise _not_found(practice_id)
    details = PracticeDetails.model_validate(card)
    details.status_order = (card.get("status") or {}).get("statusOrder")
    details.task = await _get_task(client, practice_id)
    return details


async def _get_task(client: MyItmoClient, practice_id: int) -> PracticeTask | None:
    envelope = await client.get("/practices/ind_task", params={"id": practice_id})
    raw = envelope.get("result")
    return PracticeTask.model_validate(raw) if raw else None


def _not_found(practice_id: int) -> ToolError:
    return ToolError(f"Practice {practice_id} not found")
