from __future__ import annotations

import uuid

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.agreements.models import Agreement, AgreementSignTask
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)

# Routes and shapes per go-itmo (myitmo/agreements.go), live-verify pending.
LIST_PATH = "/agreements/agreements"


def _sign_path(agreement_id: str) -> str:
    return f"/agreements/agreements/{agreement_id}/sign"


def _check_envelope(envelope, path: str):
    if not isinstance(envelope, dict):
        raise ToolError(f"Unexpected response for {path}")
    if envelope.get("error_code"):
        raise ToolError(envelope.get("error_message") or f"API error {envelope['error_code']}")
    return envelope.get("result")


async def list_agreements(client: MyItmoClient) -> list[Agreement]:
    try:
        envelope = await client.get(LIST_PATH)
    except httpx.HTTPStatusError as error:
        raise ToolError(
            f"Unavailable (HTTP {error.response.status_code}) for {LIST_PATH}"
        ) from error
    result = _check_envelope(envelope, LIST_PATH)
    return [Agreement.model_validate(raw) for raw in result or []]


async def accept_agreement(client: MyItmoClient, agreement_id: str) -> AgreementSignTask:
    # Per go-itmo (live-verify pending): POST /agreements/agreements/{id}/sign with an empty
    # JSON body and an Idempotency-Key header creates (or reuses) a sign task.
    agreement_id = agreement_id.strip()
    if not agreement_id:
        raise ToolError("agreement_id is required.")
    path = _sign_path(agreement_id)
    log.info("agreements.accept", path=path)
    response = await client.request(
        "POST",
        client.api_url(path),
        json={},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    envelope = parsed if isinstance(parsed, dict) else {}
    if response.is_error or envelope.get("error_code"):
        raise ToolError(
            envelope.get("error_message")
            or f"Agreement request rejected (HTTP {response.status_code})"
        )
    result = envelope.get("result")
    task = AgreementSignTask.model_validate(result) if isinstance(result, dict) else None
    if task is None or not (task.task_id or task.signature_id):
        raise ToolError("Could not confirm the action: unexpected server response")
    return task
