import json
from datetime import date
from pathlib import Path

import httpx
import respx

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.config import Settings
from mcp_my_itmo.features.booking import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures"
BASE = "https://my.itmo.ru/api/booking"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    from mcp_my_itmo.auth.store import TokenStore

    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_groups_parse(tmp_path):
    respx.get(f"{BASE}/dictionary/rooms/groups").respond(json=fixture("booking_groups.json"))
    client, http = await build_client(tmp_path)
    groups = await api.list_room_groups(client)
    await http.aclose()
    assert [(g.group_id, g.group_name) for g in groups][0] == (6, "Коворкинги и переговорные")
    assert groups[0].can_book_unconfirmed is True
    assert groups[1].can_book_unconfirmed is None


@respx.mock
async def test_categories_send_group_id_and_parse(tmp_path):
    route = respx.get(f"{BASE}/dictionary/rooms/categories").respond(
        json=fixture("booking_categories.json")
    )
    client, http = await build_client(tmp_path)
    categories = await api.list_room_categories(client, 6)
    await http.aclose()
    assert route.calls.last.request.url.params["groupId"] == "6"
    assert [c.category_id for c in categories] == [73, 74]
    assert categories[1].max_days == 14


@respx.mock
async def test_rooms_parse_tolerating_nulls(tmp_path):
    route = respx.get(f"{BASE}/rooms/roomsInCategory").respond(json=fixture("booking_rooms.json"))
    client, http = await build_client(tmp_path)
    rooms = await api.list_rooms_in_category(client, 73)
    await http.aclose()
    assert route.calls.last.request.url.params["categoryId"] == "73"
    assert rooms[0].room_id == 101
    assert rooms[0].category.category_id == 73
    assert rooms[0].group.group_id == 6
    assert rooms[0].max_cap == 8
    assert rooms[1].category is None
    assert rooms[1].equipment == []


@respx.mock
async def test_my_bookings_parse(tmp_path):
    route = respx.get(f"{BASE}/bookings/my").respond(json=fixture("booking_my.json"))
    client, http = await build_client(tmp_path)
    bookings = await api.list_my_bookings(client, date(2026, 10, 1), date(2026, 10, 31))
    await http.aclose()
    params = route.calls.last.request.url.params
    assert params["dateStart"] == "2026-10-01"
    assert params["dateEnd"] == "2026-10-31"
    assert len(bookings) == 1
    booking = bookings[0]
    assert booking.booking_id == 5001
    assert booking.room.room_id == 101
    assert booking.status.status_name == "Согласована"
    assert booking.start_datetime == "2026-10-13T11:30:00"
    assert booking.end_datetime == "2026-10-13T13:00:00"


@respx.mock
async def test_my_bookings_default_window_and_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("mcp_my_itmo.core.dates.date_today", lambda: date(2026, 10, 4))
    route = respx.get(f"{BASE}/bookings/my").respond(
        json={"error_code": None, "error_message": None, "result": {"count": 0, "list": []}}
    )
    client, http = await build_client(tmp_path)
    bookings = await api.list_my_bookings(client)
    await http.aclose()
    assert bookings == []
    params = route.calls.last.request.url.params
    assert params["dateStart"] == "2026-10-04"
    assert params["dateEnd"] == "2026-12-03"


@respx.mock
async def test_my_bookings_null_result(tmp_path):
    respx.get(f"{BASE}/bookings/my").respond(json={"error_code": None, "result": None})
    client, http = await build_client(tmp_path)
    assert await api.list_my_bookings(client) == []
    await http.aclose()


@respx.mock
async def test_search_rooms_sends_filters_and_returns_busy_intervals(tmp_path):
    route = respx.get(f"{BASE}/rooms/roomBookings").respond(
        json=fixture("booking_room_bookings.json")
    )
    client, http = await build_client(tmp_path)
    rooms = await api.search_rooms(client, 73, date(2026, 10, 13))
    await http.aclose()
    params = route.calls.last.request.url.params
    assert params.get_list("status") == ["1", "2", "5", "6", "8"]
    assert params["date"] == "2026-10-13"
    assert params["categoryId"] == "73"
    assert rooms[0].room_id == 101
    assert [(b.start_datetime, b.end_datetime) for b in rooms[0].busy] == [
        ("2026-10-13T09:00:00", "2026-10-13T10:00:00"),
        ("2026-10-13T11:30:00", "2026-10-13T13:00:00"),
    ]
    assert rooms[0].busy[0].status_id == 1
    assert rooms[0].busy[1].status_id == 2
    assert rooms[1].busy == []
