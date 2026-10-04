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
BASE = "https://my.itmo.ru/api/requests"


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
async def test_list_request_types_flattens_catalog(client):
    respx.get(f"{BASE}/all").respond(json=fixture("catalog.json"))
    types = await api.list_request_types(client)
    assert [(t.id, t.name, t.category_name) for t in types] == [
        (101, "Study certificate", "Certificates"),
        (102, "Military certificate", "Certificates"),
    ]


@respx.mock
async def test_list_request_types_empty(client):
    respx.get(f"{BASE}/all").respond(json={"error_code": 0, "result": None})
    assert await api.list_request_types(client) == []


@respx.mock
async def test_list_my_requests_all_and_filtered(client):
    respx.get(f"{BASE}/my").respond(json=fixture("my.json"))
    assert [r.id for r in await api.list_my_requests(client)] == [9001, 9002, 9003]
    assert [r.id for r in await api.list_my_requests(client, "done")] == [9002]
    assert [r.id for r in await api.list_my_requests(client, "In_Progress")] == [9001]


@respx.mock
async def test_list_my_requests_null_fields_tolerated_and_empty(client):
    respx.get(f"{BASE}/my").respond(json=fixture("my.json"))
    last = (await api.list_my_requests(client))[-1]
    assert last.created_at is None
    respx.get(f"{BASE}/my").respond(json={"error_code": 0, "result": None})
    assert await api.list_my_requests(client) == []


async def test_list_my_requests_unknown_status(client):
    with pytest.raises(ToolError):
        await api.list_my_requests(client, "weird")


@respx.mock
async def test_get_request_parses_detail(client):
    respx.get(f"{BASE}/my/9001").respond(json=fixture("detail.json"))
    detail = await api.get_request(client, 9001)
    assert detail.request_name == "Study certificate"
    assert detail.approvals[0].decision == "Pending"
    assert detail.entered_fields[0].data == "Embassy"


@respx.mock
async def test_get_request_not_found(client):
    respx.get(f"{BASE}/my/1").respond(404, json={})
    with pytest.raises(ToolError, match="not found"):
        await api.get_request(client, 1)
    respx.get(f"{BASE}/my/2").respond(json={"error_code": 0, "result": None})
    with pytest.raises(ToolError, match="not found"):
        await api.get_request(client, 2)


@respx.mock
async def test_get_request_form(client):
    route = respx.get(f"{BASE}/101").respond(json=fixture("form.json"))
    form = await api.get_request_form(client, 101)
    assert route.called
    assert form.user_can_apply_now is True
    assert [(f.field_id, f.field_type, f.required_field_flag) for f in form.fields] == [
        (11, "text", True),
        (12, "number", False),
    ]
    assert form.template_files == []


@respx.mock
async def test_create_request_posts_typed_values(client):
    respx.get(f"{BASE}/101").respond(json=fixture("form.json"))
    route = respx.post(f"{BASE}/send").respond(json=fixture("send_ok.json"))
    request_id = await api.create_request(client, 101, {"11": "Embassy", "12": 2})
    assert request_id == 9100
    assert json.loads(route.calls.last.request.content) == {
        "request_id": 101,
        "values": [
            {"field_id": "11", "field_type": "text", "value": "Embassy"},
            {"field_id": "12", "field_type": "number", "value": "2"},
        ],
    }


@respx.mock
async def test_create_request_unknown_field_never_posts(client):
    respx.get(f"{BASE}/101").respond(json=fixture("form.json"))
    route = respx.post(f"{BASE}/send").respond(json=fixture("send_ok.json"))
    with pytest.raises(ToolError, match="99"):
        await api.create_request(client, 101, {"99": "x"})
    assert not route.called


@respx.mock
async def test_create_request_blocked_form_never_posts(client):
    blocked = fixture("form.json")
    blocked["result"]["user_can_apply_now"] = False
    blocked["result"]["user_cannot_apply_now_reason"] = "Too early"
    respx.get(f"{BASE}/101").respond(json=blocked)
    route = respx.post(f"{BASE}/send").respond(json=fixture("send_ok.json"))
    with pytest.raises(ToolError, match="Too early"):
        await api.create_request(client, 101, {})
    assert not route.called


@respx.mock
async def test_create_request_rejection_lists_field_errors(client):
    respx.get(f"{BASE}/101").respond(json=fixture("form.json"))
    respx.post(f"{BASE}/send").respond(json=fixture("send_rejected.json"))
    with pytest.raises(ToolError, match="Validation failed.*Field is required"):
        await api.create_request(client, 101, {})


@respx.mock
async def test_create_request_http_error_is_tool_error(client):
    respx.get(f"{BASE}/101").respond(json=fixture("form.json"))
    respx.post(f"{BASE}/send").respond(500, text="boom")
    with pytest.raises(ToolError):
        await api.create_request(client, 101, {})


@respx.mock
async def test_create_request_without_id_in_reply_fails(client):
    respx.get(f"{BASE}/101").respond(json=fixture("form.json"))
    respx.post(f"{BASE}/send").respond(json={"error_code": 0, "result": {}})
    with pytest.raises(ToolError, match="not created"):
        await api.create_request(client, 101, {})
