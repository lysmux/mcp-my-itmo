import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.requests import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "requests"
BASE = "https://my.itmo.ru/api/queues"
OK = {"error_code": 0, "error_message": None, "result": None}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
async def client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    yield MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http)
    await http.aclose()


@respx.mock
async def test_list_queues_attaches_my_entries(client):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    queues = await api.list_queues(client)
    assert [q.table_id for q in queues] == [7, 8]
    assert [e.application_id for e in queues[0].my_entries] == [501]
    assert queues[1].my_entries == []
    assert queues[1].template_id == 55
    assert queues[1].table_address is None


@respx.mock
async def test_list_queues_empty(client):
    respx.get(f"{BASE}/").respond(json={"error_code": 0, "result": None})
    respx.get(f"{BASE}/current").respond(json={"error_code": 0, "result": None})
    assert await api.list_queues(client) == []


@respx.mock
async def test_get_queue_includes_slots(client):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    slots = respx.get(f"{BASE}/slots", params={"table_id": 7, "type_id": 2}).respond(
        json=fixture("queues_slots.json")
    )
    queue = await api.get_queue(client, 7)
    assert slots.called
    assert queue.table_name == "Dean office"
    assert [s.time_table_id for s in queue.slots] == [3001, 3002]
    assert queue.my_entries[0].application_id == 501


@respx.mock
async def test_get_queue_not_found(client):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    with pytest.raises(ToolError, match="not found"):
        await api.get_queue(client, 999)


@respx.mock
async def test_join_queue_posts_signup_body(client):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    route = respx.post(f"{BASE}/").respond(json=OK)
    await api.join_queue(client, 7, 3001, "+7(900)000-00-00", comment="hi")
    sent = route.calls.last.request
    assert sent.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert sent.headers["Authorization"].startswith("Bearer ")
    assert json.loads(sent.content) == {
        "time_table_id": 3001,
        "phone": "+7(900)000-00-00",
        "comment": "hi",
        "request_id": None,
    }


@respx.mock
async def test_join_unknown_queue_never_posts(client):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    route = respx.post(f"{BASE}/").respond(json=OK)
    with pytest.raises(ToolError, match="not found"):
        await api.join_queue(client, 999, 1, "+7(900)000-00-00")
    assert not route.called


@respx.mock
async def test_join_queue_rejection(client):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    respx.post(f"{BASE}/").respond(json={"error_code": 3, "error_message": "Slot taken"})
    with pytest.raises(ToolError, match="Slot taken"):
        await api.join_queue(client, 7, 3001, "+7(900)000-00-00")


@respx.mock
async def test_leave_queue_sends_delete_body(client):
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    route = respx.delete(f"{BASE}/").respond(json=OK)
    await api.leave_queue(client, 501)
    assert json.loads(route.calls.last.request.content) == {
        "type_id": 2,
        "application_id": 501,
    }


@respx.mock
async def test_leave_queue_unknown_entry_never_deletes(client):
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    route = respx.delete(f"{BASE}/").respond(json=OK)
    with pytest.raises(ToolError, match="not found"):
        await api.leave_queue(client, 1)
    assert not route.called


@respx.mock
async def test_leave_queue_rejection(client):
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    respx.delete(f"{BASE}/").respond(json={"error_code": 4, "error_message": "Too late"})
    with pytest.raises(ToolError, match="Too late"):
        await api.leave_queue(client, 501)


UNCONFIRMED = [
    httpx.Response(200, text=""),
    httpx.Response(200, text="<html></html>"),
    httpx.Response(200, json=[1]),
]


@respx.mock
@pytest.mark.parametrize("response", UNCONFIRMED)
async def test_join_queue_without_json_object_raises(client, response):
    respx.get(f"{BASE}/").respond(json=fixture("queues.json"))
    respx.post(f"{BASE}/").mock(return_value=response)
    with pytest.raises(ToolError, match="Could not confirm"):
        await api.join_queue(client, 7, 3001, "+7(900)000-00-00")


@respx.mock
@pytest.mark.parametrize("response", UNCONFIRMED)
async def test_leave_queue_without_json_object_raises(client, response):
    respx.get(f"{BASE}/current").respond(json=fixture("queues_current.json"))
    respx.delete(f"{BASE}/").mock(return_value=response)
    with pytest.raises(ToolError, match="Could not confirm"):
        await api.leave_queue(client, 501)
