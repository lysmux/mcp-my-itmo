import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.dashboard import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "dashboard"
BASE = "https://my.itmo.ru/api/system"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_dashboard_parses_widgets_ignoring_extras(tmp_path):
    route = respx.get(f"{BASE}/dashboard").respond(json=fixture("dashboard.json"))
    client, http = await build_client(tmp_path)

    widgets = await api.get_dashboard(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/system/dashboard"
    assert widgets[0].widget == "ScholarshipWidget"
    assert widgets[0].max_w is None


@respx.mock
async def test_menu_tolerates_null_children_and_description(tmp_path):
    route = respx.get(f"{BASE}/v1/menu/items").respond(json=fixture("menu.json"))
    client, http = await build_client(tmp_path)

    items = await api.get_menu(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/system/v1/menu/items"
    assert items[0].description is None
    assert items[0].children[0].children == []


@respx.mock
async def test_empty_result_is_empty_list(tmp_path):
    respx.get(f"{BASE}/dashboard").respond(json={"error_code": 0, "result": None})
    respx.get(f"{BASE}/v1/menu/items").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    assert await api.get_dashboard(client) == []
    assert await api.get_menu(client) == []
    await http.aclose()


@respx.mock
async def test_error_code_raises_tool_error(tmp_path):
    respx.get(f"{BASE}/dashboard").respond(json={"error_code": 5, "error_message": "boom"})
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="boom"):
        await api.get_dashboard(client)
    await http.aclose()
