from __future__ import annotations

from datetime import date, timedelta

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core import dates
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import unwrap_result
from mcp_my_itmo.features.booking.models import (
    Booking,
    Room,
    RoomAvailability,
    RoomCategory,
    RoomGroup,
)
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)

_ACTIVE_BOOKING_STATUSES = (1, 2, 5, 6, 8)
_DEFAULT_BOOKINGS_WINDOW_DAYS = 60


async def list_room_groups(client: MyItmoClient) -> list[RoomGroup]:
    envelope = await client.get("/booking/dictionary/rooms/groups")
    return [RoomGroup.model_validate(raw) for raw in unwrap_result(envelope)]


async def list_room_categories(client: MyItmoClient, group_id: int) -> list[RoomCategory]:
    envelope = await client.get("/booking/dictionary/rooms/categories", {"groupId": group_id})
    return [RoomCategory.model_validate(raw) for raw in unwrap_result(envelope)]


async def list_rooms_in_category(client: MyItmoClient, category_id: int) -> list[Room]:
    envelope = await client.get("/booking/rooms/roomsInCategory", {"categoryId": category_id})
    return [Room.model_validate(raw) for raw in unwrap_result(envelope)]


async def search_rooms(
    client: MyItmoClient, category_id: int, day: date
) -> list[RoomAvailability]:
    """Rooms of a category with their existing bookings on ``day`` (busy intervals)."""
    params = {
        "status": list(_ACTIVE_BOOKING_STATUSES),
        "date": day.isoformat(),
        "categoryId": category_id,
    }
    envelope = await client.get("/booking/rooms/roomBookings", params)
    return [RoomAvailability.from_raw(raw) for raw in unwrap_result(envelope)]


async def list_my_bookings(
    client: MyItmoClient, date_start: date | None = None, date_end: date | None = None
) -> list[Booking]:
    if date_start is None:
        date_start = dates.date_today()
    if date_end is None:
        date_end = date_start + timedelta(days=_DEFAULT_BOOKINGS_WINDOW_DAYS)
    envelope = await client.get(
        "/booking/bookings/my",
        {"dateStart": date_start.isoformat(), "dateEnd": date_end.isoformat()},
    )
    result = envelope.get("result") or {}
    return [Booking.model_validate(raw) for raw in result.get("list") or []]


async def create_booking(
    client: MyItmoClient,
    room_id: int,
    day: date,
    time_from: str,
    time_to: str,
    name: str | None = None,
    participants: int = 1,
    contact_phone: str | None = None,
) -> dict:
    # Request shape per go-itmo myitmo/booking.go: POST .../booking/bookings/ (trailing slash)
    # with a one-element JSON array; success has an empty body. Still live-verify on the
    # first successful real booking.
    booking = {
        "name": name or "",
        "additional_info": "",
        "participants": participants,
        "contact_phone": contact_phone or "",
        "event_id": None,
        "co_bookers": [],
        "start_datetime": _booking_datetime(day, time_from),
        "end_datetime": _booking_datetime(day, time_to),
        "room_id": room_id,
        "equipment": [],
        "tech_support": False,
    }
    log.info("booking.create", room_id=room_id, day=day.isoformat())
    response = await client.request(
        "POST", client.api_url("/booking/bookings/"), json=[booking]
    )
    _write_envelope(response)
    return booking


async def cancel_booking(client: MyItmoClient, booking_id: int) -> bool:
    # DELETE {api_base}/booking/bookings/{id}, matching go-itmo (booking.go).
    log.info("booking.cancel", booking_id=booking_id)
    response = await client.request(
        "DELETE", client.api_url(f"/booking/bookings/{booking_id}")
    )
    if response.status_code == 404:
        raise ToolError(f"Booking {booking_id} not found")
    _write_envelope(response)
    return True


def _booking_datetime(day: date, clock: str) -> str:
    return f"{day.isoformat()} {clock[:5]}"


def _write_envelope(response: httpx.Response) -> dict:
    """Unwrap a write response, turning server rejections into ToolError."""
    try:
        envelope = response.json()
    except ValueError:
        envelope = {}
    if not isinstance(envelope, dict):
        envelope = {}
    message = envelope.get("error_message")
    if response.is_error or envelope.get("error_code"):
        raise ToolError(
            message or f"Booking request rejected (HTTP {response.status_code})"
        )
    return envelope
