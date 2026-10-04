import json
from datetime import date
from pathlib import Path

import httpx
import respx

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.dates import current_week
from mcp_my_itmo.config import Settings
from mcp_my_itmo.features.timetable import api
from mcp_my_itmo.features.timetable.models import ScheduleWeek
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures"
SCHEDULE_URL = "https://my.itmo.ru/api/schedule/schedule/personal"
SLOTS_URL = "https://my.itmo.ru/api/schedule/meta/time_slots"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    from mcp_my_itmo.auth.store import TokenStore

    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_parses_days_with_lessons(tmp_path):
    respx.get(SCHEDULE_URL).respond(json=fixture("schedule_personal.json"))
    client, http = await build_client(tmp_path)

    week = await api.get_schedule(client, date(2026, 9, 28), date(2026, 10, 4))
    await http.aclose()

    assert len(week.days) == 7
    first = week.days[0].lessons[0]
    assert week.days[0].day == date(2026, 9, 28)
    assert first.subject == "Операционные системы"
    assert first.type == "Лекция"
    assert (first.time_start, first.time_end) == ("11:30", "13:00")
    assert first.teacher_name == "Иванов Иван Иванович"
    assert first.room == "1234"
    assert week.days[0].lessons[1].room is None


@respx.mock
async def test_default_range_is_current_week(tmp_path, monkeypatch):
    route = respx.get(SCHEDULE_URL).respond(json={"code": 0, "message": None, "data": []})
    client, http = await build_client(tmp_path)
    monkeypatch.setattr("mcp_my_itmo.core.dates.date_today", lambda: date(2026, 10, 1))

    await api.get_schedule(client)
    await http.aclose()

    params = route.calls.last.request.url.params
    assert params["date_start"] == "2026-09-28"
    assert params["date_end"] == "2026-10-04"


def test_current_week_is_monday_to_sunday():
    assert current_week(date(2026, 10, 4)) == (date(2026, 9, 28), date(2026, 10, 4))
    assert current_week(date(2026, 9, 28)) == (date(2026, 9, 28), date(2026, 10, 4))


def test_days_with_empty_lessons_yield_no_lessons():
    envelope = {"code": 0, "data": [{"date": "2026-09-28", "lessons": []}]}

    week = ScheduleWeek.from_envelope(envelope)

    assert [day.lessons for day in week.days] == [[]]


def test_empty_or_null_data_yields_empty_schedule():
    assert ScheduleWeek.from_envelope({"code": 0, "data": []}).days == []
    assert ScheduleWeek.from_envelope({"code": 0, "data": None}).days == []


@respx.mock
async def test_time_slots_parse(tmp_path):
    respx.get(SLOTS_URL).respond(json=fixture("time_slots.json"))
    client, http = await build_client(tmp_path)

    slots = await api.get_time_slots(client)
    await http.aclose()

    assert len(slots) == 8
    assert (slots[0].order, slots[0].time_start, slots[0].time_end) == (1, "08:10", "09:40")


def test_null_lessons_yield_empty_day():
    envelope = {"code": 0, "data": [{"date": "2026-09-28", "lessons": None}]}

    assert ScheduleWeek.from_envelope(envelope).days[0].lessons == []
