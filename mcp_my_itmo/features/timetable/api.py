from __future__ import annotations

from datetime import date

from mcp_my_itmo.core import dates
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import unwrap_data
from mcp_my_itmo.features.timetable.models import ScheduleWeek, TimeSlot


async def get_schedule(
    client: MyItmoClient, date_start: date | None = None, date_end: date | None = None
) -> ScheduleWeek:
    if date_start is None and date_end is None:
        date_start, date_end = dates.current_week(dates.date_today())
    params = {
        "date_start": date_start.isoformat() if date_start else None,
        "date_end": date_end.isoformat() if date_end else None,
    }
    envelope = await client.get("/schedule/schedule/personal", params)
    return ScheduleWeek.from_envelope(envelope)


async def get_time_slots(client: MyItmoClient) -> list[TimeSlot]:
    envelope = await client.get("/schedule/meta/time_slots")
    return [TimeSlot.model_validate(raw) for raw in unwrap_data(envelope)]
