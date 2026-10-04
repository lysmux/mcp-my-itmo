from __future__ import annotations

import json

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.requests.models import (
    Queue,
    QueueEntry,
    QueueSlot,
    RequestDetail,
    RequestForm,
    RequestSummary,
    RequestType,
)
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)

# Routes and shapes per go-itmo (myitmo/requests.go, myitmo/queues.go), live-verify pending.
# Legacy /api/requests (student templates + own requests) and /api/queues (electronic queues).
# Admin and requests/v2 operations are intentionally not exposed.
_STATUS_BY_NAME = {"in_progress": 0, "done": 1, "rejected": 2}


async def _read(client: MyItmoClient, path: str, params: dict | None = None):
    """GET a ``{error_code, error_message, result}`` envelope; None when the server says 404."""
    try:
        envelope = await client.get(path, params)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            return None
        raise ToolError(
            f"Unavailable (HTTP {error.response.status_code}) for {path}"
        ) from error
    if envelope.get("error_code"):
        raise ToolError(envelope.get("error_message") or f"API error {envelope['error_code']}")
    return envelope.get("result")


def _write_envelope(response: httpx.Response) -> dict:
    """Unwrap a write response, turning rejections and unconfirmed answers into ToolError."""
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    envelope = parsed if isinstance(parsed, dict) else {}
    if response.is_error or envelope.get("error_code"):
        message = (
            envelope.get("error_message")
            or envelope.get("message")
            or f"Request rejected (HTTP {response.status_code})"
        )
        raise ToolError(_with_field_errors(message, envelope.get("result")))
    if not isinstance(parsed, dict):
        raise ToolError("Could not confirm the action: unexpected server response")
    return envelope


def _with_field_errors(message: str, result) -> str:
    errors = result.get("error_list") if isinstance(result, dict) else None
    details = [
        f"field {item.get('id')}: {(item.get('error_info') or {}).get('text')}"
        for item in errors or []
    ]
    return f"{message} ({'; '.join(details)})" if details else message


async def list_request_types(client: MyItmoClient) -> list[RequestType]:
    result = await _read(client, "/requests/all")
    return [
        RequestType.model_validate({**template, "category_name": category.get("name")})
        for category in result or []
        for template in category.get("requests") or []
    ]


async def list_my_requests(
    client: MyItmoClient, status: str | None = None
) -> list[RequestSummary]:
    wanted = None
    if status:
        wanted = _STATUS_BY_NAME.get(status.lower())
        if wanted is None:
            raise ToolError(
                f"Unknown status {status!r}; use one of: {', '.join(_STATUS_BY_NAME)}."
            )
    requests = [
        RequestSummary.model_validate(raw) for raw in await _read(client, "/requests/my") or []
    ]
    return [r for r in requests if wanted is None or r.status == wanted]


async def get_request(client: MyItmoClient, request_id: int) -> RequestDetail:
    result = await _read(client, f"/requests/my/{request_id}")
    if not result:
        raise ToolError(f"Request {request_id} not found")
    return RequestDetail.model_validate(result)


async def get_request_form(client: MyItmoClient, type_id: int) -> RequestForm:
    result = await _read(client, f"/requests/{type_id}")
    if not result:
        raise ToolError(f"Request type {type_id} not found")
    return RequestForm.model_validate(result)


async def create_request(client: MyItmoClient, type_id: int, params: dict) -> int:
    """Submit a request of ``type_id``; ``params`` maps form field ids to values."""
    form = await get_request_form(client, type_id)
    if not form.user_can_apply_now:
        raise ToolError(
            form.user_cannot_apply_now_reason or f"Request type {type_id} cannot be created now"
        )
    types_by_id = {str(field.field_id): field.field_type for field in form.fields}
    unknown = [key for key in params if str(key) not in types_by_id]
    if unknown:
        raise ToolError(f"Unknown field ids {unknown}; the form has: {sorted(types_by_id)}")
    body = {
        "request_id": type_id,
        "values": [
            {
                "field_id": str(key),
                "field_type": types_by_id[str(key)],
                "value": "" if value is None else str(value),
            }
            for key, value in params.items()
        ],
    }
    log.info("requests.create", type_id=type_id)
    # ASSUMED request shape per go-itmo, live-verify pending: POST /requests/send.
    response = await client.request("POST", client.api_url("/requests/send"), json=body)
    result = _write_envelope(response).get("result") or {}
    if result.get("reqId") is None:
        raise ToolError("Request was not created")
    return result["reqId"]


async def _my_entries(client: MyItmoClient) -> list[QueueEntry]:
    result = await _read(client, "/queues/current")
    return [QueueEntry.model_validate(raw) for raw in result or []]


async def _all_queues(client: MyItmoClient) -> list[Queue]:
    result = await _read(client, "/queues/")
    return [Queue.model_validate(raw) for raw in result or []]


async def list_queues(client: MyItmoClient) -> list[Queue]:
    queues = await _all_queues(client)
    entries = await _my_entries(client)
    for queue in queues:
        queue.my_entries = [
            e for e in entries if (e.table_id, e.type_id) == (queue.table_id, queue.type_id)
        ]
    return queues


async def get_queue(client: MyItmoClient, queue_id: int) -> Queue:
    queue = next((q for q in await list_queues(client) if q.table_id == queue_id), None)
    if queue is None:
        raise ToolError(f"Queue {queue_id} not found")
    result = await _read(
        client, "/queues/slots", {"table_id": queue.table_id, "type_id": queue.type_id}
    )
    queue.slots = [QueueSlot.model_validate(raw) for raw in result or []]
    return queue


async def join_queue(
    client: MyItmoClient,
    queue_id: int,
    time_table_id: int,
    phone: str,
    comment: str | None = None,
    request_id: int | None = None,
) -> None:
    if not any(q.table_id == queue_id for q in await _all_queues(client)):
        raise ToolError(f"Queue {queue_id} not found")
    body = {
        "time_table_id": time_table_id,
        "phone": phone,
        "comment": comment,
        "request_id": request_id,
    }
    log.info("queues.join", queue_id=queue_id, time_table_id=time_table_id)
    # go-itmo (queues.go) sends the JSON string with a form-urlencoded content type.
    response = await client.request(
        "POST",
        client.api_url("/queues/"),
        content=json.dumps(body),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    _write_envelope(response)


async def leave_queue(client: MyItmoClient, application_id: int) -> None:
    entry = next(
        (e for e in await _my_entries(client) if e.application_id == application_id), None
    )
    if entry is None:
        raise ToolError(f"Queue sign-up {application_id} not found")
    body = {"type_id": entry.type_id, "application_id": application_id}
    log.info("queues.leave", application_id=application_id)
    # ASSUMED, live-verify pending: DELETE /queues/ with a JSON body per go-itmo.
    response = await client.request("DELETE", client.api_url("/queues/"), json=body)
    _write_envelope(response)
