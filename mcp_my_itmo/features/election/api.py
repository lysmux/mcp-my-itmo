from __future__ import annotations

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.election.models import (
    ElectionAvailability,
    ElectionDiscipline,
    ElectionFlowChain,
    ElectiveClash,
    ElectiveCurrent,
    ElectiveNode,
    ElectivePeriod,
)
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)

# Routes and shapes per go-itmo (myitmo/election.go, myitmo/elective.go), live-verify pending.
# /api/election is a two-stage discipline-then-flow campaign (read-only here);
# /api/intro and /api/facultative share one flow booking API (read + gated writes).
ELECTION = "election"
ELECTIVE_KINDS = ("intro", "facultative")
ALL_KINDS = (ELECTION, *ELECTIVE_KINDS)
_CLASH_ERROR_CODE = 109
_CONFIRMED = 2


def _require_kind(kind: str, allowed: tuple[str, ...]) -> None:
    if kind not in allowed:
        raise ToolError(f"Unknown kind {kind!r}; use one of: {', '.join(allowed)}.")


def _elective_path(kind: str, suffix: str) -> str:
    return f"/{kind}/{suffix}"


async def _read(client: MyItmoClient, path: str):
    try:
        envelope = await client.get(path)
    except httpx.HTTPStatusError as error:
        raise ToolError(
            f"Unavailable (HTTP {error.response.status_code}) for {path}"
        ) from error
    if envelope.get("error_code"):
        raise ToolError(envelope.get("error_message") or f"API error {envelope['error_code']}")
    return envelope.get("result")


async def list_election_offers(
    client: MyItmoClient, kind: str = ELECTION
) -> list[ElectionDiscipline] | list[ElectiveNode]:
    _require_kind(kind, ALL_KINDS)
    if kind == ELECTION:
        result = await _read(client, "/election/students/available_disciplines")
        return [ElectionDiscipline.model_validate(raw) for raw in result or []]
    result = await _read(client, _elective_path(kind, "json/"))
    return [ElectiveNode.model_validate(raw) for raw in (result or {}).get("json") or []]


async def _election_section(client: MyItmoClient) -> dict:
    availability = await _read(client, "/election/students/availability")
    chosen = await _read(client, "/election/students/chosen_flows")
    chains = await _read(client, "/election/students/ordered_flow_chains")
    return {
        "availability": ElectionAvailability.model_validate(availability or {}).model_dump(
            exclude_none=True
        ),
        "chosen_flow_ids": chosen or [],
        "chains": [
            ElectionFlowChain.model_validate(raw).model_dump(exclude_none=True)
            for raw in chains or []
        ],
    }


async def _current(client: MyItmoClient, kind: str) -> ElectiveCurrent:
    result = await _read(client, _elective_path(kind, "current/"))
    return ElectiveCurrent.model_validate(result or {})


async def _elective_section(client: MyItmoClient, kind: str) -> dict:
    status = await _read(client, _elective_path(kind, "status/"))
    semester = (status or {}).get("semester")
    current = await _current(client, kind)
    return {
        "period": ElectivePeriod.model_validate(semester).model_dump(exclude_none=True)
        if semester
        else None,
        "current": current.model_dump(exclude_none=True),
    }


async def get_my_elections(client: MyItmoClient) -> dict:
    """Own state per election flow; a flow the student cannot access reports an error only."""
    sections: dict[str, dict] = {}
    for kind in ALL_KINDS:
        try:
            if kind == ELECTION:
                sections[kind] = await _election_section(client)
            else:
                sections[kind] = await _elective_section(client, kind)
        except ToolError as error:
            sections[kind] = {"error": f"Section unavailable: {error}"}
    return sections


async def choose_flow(client: MyItmoClient, kind: str, flow_id: int) -> None:
    # ASSUMED per go-itmo (live-verify pending): POST /{intro|facultative}/booking/
    # body {"selected_flows": [...], "canceled_flows": [...]}; books but does not confirm.
    await _book(client, kind, selected=[flow_id], canceled=[])


async def withdraw_flow(client: MyItmoClient, kind: str, flow_id: int) -> None:
    # Same booking endpoint; the flow goes into canceled_flows (per go-itmo, live-verify pending).
    await _book(client, kind, selected=[], canceled=[flow_id])


async def confirm_choice(client: MyItmoClient, kind: str) -> None:
    # ASSUMED per go-itmo (live-verify pending): POST /{intro|facultative}/commit/
    # body {"status": 2, "flow_id": [all currently selected flows]}.
    _require_kind(kind, ELECTIVE_KINDS)
    current = await _current(client, kind)
    await _write(
        client,
        _elective_path(kind, "commit/"),
        {"status": _CONFIRMED, "flow_id": current.flow_id},
    )


async def _book(client: MyItmoClient, kind: str, selected: list[int], canceled: list[int]) -> None:
    _require_kind(kind, ELECTIVE_KINDS)
    body = {"selected_flows": selected, "canceled_flows": canceled}
    await _write(client, _elective_path(kind, "booking/"), body)


async def _write(client: MyItmoClient, path: str, body: dict):
    log.info("election.write", path=path)
    response = await client.request("POST", client.api_url(path), json=body)
    try:
        envelope = response.json()
    except ValueError:
        envelope = {}
    if not isinstance(envelope, dict):
        envelope = {}
    code = envelope.get("error_code")
    if code == _CLASH_ERROR_CODE:
        raise ToolError(_clash_message(envelope))
    if response.is_error or code:
        raise ToolError(
            envelope.get("error_message")
            or f"Election request rejected (HTTP {response.status_code})"
        )
    return envelope.get("result")


def _clash_message(envelope: dict) -> str:
    clashes = [ElectiveClash.model_validate(raw) for raw in envelope.get("result") or []]
    pairs = ", ".join(
        f"{(c.flow1.flow_id if c.flow1 else '?')} vs {(c.flow2.flow_id if c.flow2 else '?')}"
        for c in clashes
    )
    reason = envelope.get("error_message") or "timetable clash"
    return f"Flows were booked but clash with the timetable ({reason}): {pairs}"
