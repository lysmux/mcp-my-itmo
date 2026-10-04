import json
from datetime import date

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.config import Settings
from mcp_my_itmo.features.booking import api
from tests.core.test_client import FakeAuth, make_tokens

BOOKINGS_URL = "https://my.itmo.ru/api/booking/bookings"
CREATE_URL = BOOKINGS_URL + "/"

async def build_client(tmp_path, auth=None):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, auth or FakeAuth(make_tokens("x")), http), http


async def create(client):
    return await api.create_booking(
        client, 101, date(2026, 10, 10), "10:00", "11:00", name="Study", participants=2
    )


@respx.mock
async def test_create_booking_posts_one_element_array_to_slash_url(tmp_path):
    route = respx.post(CREATE_URL).respond(204)
    client, http = await build_client(tmp_path)
    created = await create(client)
    await http.aclose()
    request = route.calls.last.request
    assert request.url.path.endswith("/booking/bookings/")
    assert json.loads(request.content) == [
        {
            "name": "Study",
            "additional_info": "",
            "participants": 2,
            "contact_phone": "",
            "event_id": None,
            "co_bookers": [],
            "start_datetime": "2026-10-10 10:00",
            "end_datetime": "2026-10-10 11:00",
            "room_id": 101,
            "equipment": [],
            "tech_support": False,
        }
    ]
    assert created["room_id"] == 101
    assert created["start_datetime"] == "2026-10-10 10:00"


@respx.mock
async def test_create_booking_strips_seconds_from_times(tmp_path):
    route = respx.post(CREATE_URL).respond(200)
    client, http = await build_client(tmp_path)
    await api.create_booking(client, 101, date(2026, 10, 10), "10:00:00", "11:30:00")
    await http.aclose()
    body = json.loads(route.calls.last.request.content)[0]
    assert body["start_datetime"] == "2026-10-10 10:00"
    assert body["end_datetime"] == "2026-10-10 11:30"


@respx.mock
async def test_create_booking_envelope_error_raises_tool_error(tmp_path):
    respx.post(CREATE_URL).respond(
        json={"error_code": 5, "error_message": "Slot is taken", "result": None}
    )
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="Slot is taken"):
        await create(client)
    await http.aclose()


@respx.mock
async def test_create_booking_http_409_raises_tool_error(tmp_path):
    respx.post(CREATE_URL).respond(
        409, json={"error_code": 409, "error_message": "Room already booked"}
    )
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="Room already booked"):
        await create(client)
    await http.aclose()


@respx.mock
async def test_cancel_booking_issues_delete_and_returns_true(tmp_path):
    route = respx.delete(f"{BOOKINGS_URL}/777").respond(
        json={"error_code": None, "error_message": None, "result": None}
    )
    client, http = await build_client(tmp_path)
    cancelled = await api.cancel_booking(client, 777)
    await http.aclose()
    assert route.called
    assert cancelled is True


@respx.mock
async def test_cancel_booking_404_raises_tool_error(tmp_path):
    respx.delete(f"{BOOKINGS_URL}/999").respond(404)
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="Booking 999 not found"):
        await api.cancel_booking(client, 999)
    await http.aclose()


@respx.mock
async def test_write_refreshes_once_on_401_and_retries(tmp_path):
    route = respx.post(CREATE_URL).mock(
        side_effect=[httpx.Response(401), httpx.Response(204)]
    )
    auth = FakeAuth(make_tokens("access-2"))
    client, http = await build_client(tmp_path, auth)
    created = await create(client)
    await http.aclose()
    assert route.call_count == 2
    assert len(auth.calls) == 1
    assert route.calls.last.request.headers["Authorization"] == "Bearer access-2"
    assert created["room_id"] == 101
