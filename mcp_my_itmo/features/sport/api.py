from __future__ import annotations

from datetime import date, timedelta

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core import dates
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.sport.models import (
    SportAttempts,
    SportDebt,
    SportScheduleDay,
    SportScore,
    SportSemester,
    SportSummary,
)
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)

# Routes and shapes per go-itmo (myitmo/sport.go, base /api/sport), live-verify pending.
_DEFAULT_WINDOW_DAYS = 7
_ALL_BUILDINGS = 0


def _checked(envelope: dict) -> dict:
    if envelope.get("error_code"):
        raise ToolError(
            envelope.get("error_message") or f"Sport API error {envelope['error_code']}"
        )
    return envelope


async def _read_result(client: MyItmoClient, path: str, params: dict | None = None):
    return _checked(await client.get(path, params)).get("result")


async def get_my_sport(client: MyItmoClient) -> SportSummary:
    semester_raw = await _read_result(client, "/sport/semesters/current")
    semester = SportSemester.model_validate(semester_raw) if semester_raw else None
    score = None
    if semester is not None:
        score_raw = await _read_result(
            client, "/sport/personal/score", {"semester_id": semester.id}
        )
        score = SportScore.model_validate(score_raw or {})
    attempts_raw = await _read_result(client, "/sport/personal/have_attempts")
    debt_raw = await _read_result(client, "/sport/personal/debt")
    return SportSummary(
        semester=semester,
        score=score,
        attempts=SportAttempts.model_validate(attempts_raw) if attempts_raw else None,
        debt=SportDebt.model_validate(debt_raw) if debt_raw else None,
    )


async def list_sport_sections(
    client: MyItmoClient,
    date_from: date | None = None,
    date_to: date | None = None,
    building_id: int = _ALL_BUILDINGS,
    sport_type_ids: list[int] | None = None,
) -> list[SportScheduleDay]:
    """Lessons open for sign-up (sections, groups, times, free places)."""
    start, end = _window(date_from, date_to)
    params: dict = {
        "date_start": start.isoformat(),
        "date_end": end.isoformat(),
        "building_id": building_id,
    }
    if sport_type_ids:
        params["sport_type_id"] = sport_type_ids
    return _days(await _read_result(client, "/sport/sign/schedule", params))


async def get_sport_schedule(
    client: MyItmoClient, date_from: date | None = None, date_to: date | None = None
) -> list[SportScheduleDay]:
    start, end = _window(date_from, date_to)
    params = {"date_start": start.isoformat(), "date_end": end.isoformat()}
    return _days(await _read_result(client, "/sport/personal/calendar", params))


def _window(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    start = date_from or dates.date_today()
    end = date_to or start + timedelta(days=_DEFAULT_WINDOW_DAYS)
    if end < start:
        raise ToolError("date_to must not be before date_from.")
    return start, end


def _days(result) -> list[SportScheduleDay]:
    return [SportScheduleDay.model_validate(raw) for raw in result or []]


async def enroll_lessons(client: MyItmoClient, lesson_ids: list[int]):
    # ASSUMED per go-itmo (live-verify pending): POST /sport/sign/schedule/lessons, body = JSON array of ids.
    return await _write(client, "POST", "/sport/sign/schedule/lessons", list(lesson_ids))


async def cancel_lessons(client: MyItmoClient, lesson_ids: list[int]):
    # ASSUMED per go-itmo (live-verify pending): DELETE /sport/sign/schedule/lessons, body = JSON array of ids.
    return await _write(client, "DELETE", "/sport/sign/schedule/lessons", list(lesson_ids))


async def enroll_group(client: MyItmoClient, lesson_group_id: int) -> None:
    # ASSUMED per go-itmo (live-verify pending): POST /sport/sign/schedule/lesson_groups/{id}, no body.
    await _write(client, "POST", f"/sport/sign/schedule/lesson_groups/{lesson_group_id}")


async def cancel_group(client: MyItmoClient, lesson_group_id: int) -> None:
    # ASSUMED per go-itmo (live-verify pending): DELETE /sport/sign/schedule/lesson_groups/{id}.
    await _write(client, "DELETE", f"/sport/sign/schedule/lesson_groups/{lesson_group_id}")


async def _write(client: MyItmoClient, method: str, path: str, body=None):
    log.info("sport.write", method=method, path=path)
    response = await client.request(method, client.api_url(path), json=body)
    return _write_result(response)


def _write_result(response: httpx.Response):
    """Unwrap a write response, turning rejections and unconfirmed answers into ToolError."""
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    envelope = parsed if isinstance(parsed, dict) else {}
    if response.is_error or envelope.get("error_code"):
        raise ToolError(
            envelope.get("error_message")
            or f"Sport request rejected (HTTP {response.status_code})"
        )
    if not isinstance(parsed, dict):
        raise ToolError("Could not confirm the action: unexpected server response")
    return envelope.get("result")
