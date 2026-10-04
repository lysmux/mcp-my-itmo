import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.practices import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "practices"
BASE = "https://my.itmo.ru/api/practices"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_list_parses_years_and_tolerates_nulls(tmp_path):
    route = respx.get(f"{BASE}/practices/all").respond(json=fixture("list.json"))
    client, http = await build_client(tmp_path)

    years = await api.get_practices(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/practices/practices/all"
    assert [year.year for year in years] == ["2", "3"]
    current, graded = years[0].practices
    assert (current.id, current.is_current, current.mark, current.badge_color) == (501, True, None, "Yellow")
    assert (graded.mark, graded.head_name, graded.date_from) == ("Excellent", None, None)
    assert years[1].practices == []


@respx.mock
async def test_empty_list_yields_empty_list(tmp_path):
    respx.get(f"{BASE}/practices/all").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    assert await api.get_practices(client) == []
    await http.aclose()


@respx.mock
async def test_practice_combines_details_and_assignment(tmp_path):
    details = respx.get(f"{BASE}/practices", params={"id": "501"}).respond(json=fixture("detail.json"))
    task = respx.get(f"{BASE}/ind_task", params={"id": "501"}).respond(json=fixture("task.json"))
    client, http = await build_client(tmp_path)

    practice = await api.get_practice(client, 501)
    await http.aclose()

    assert details.calls.last.request.url.path == "/api/practices/practices"
    assert task.calls.last.request.url.path == "/api/practices/ind_task"
    assert (practice.name, practice.status_order, practice.head_itmo_isu) == ("Industrial practice", 4, 100002)
    assert practice.curator_photo is None
    assert practice.task.topic == "Backend service"
    assert [stage.duration for stage in practice.task.stages] == [None, 14]
    assert practice.task.stages[1].stage_task is None


@respx.mock
async def test_practice_without_assignment_has_no_task(tmp_path):
    respx.get(f"{BASE}/practices").respond(json=fixture("detail.json"))
    respx.get(f"{BASE}/ind_task").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    practice = await api.get_practice(client, 501)
    await http.aclose()

    assert practice.task is None


@respx.mock
async def test_unknown_practice_raises_tool_error(tmp_path):
    respx.get(f"{BASE}/practices").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="not found"):
        await api.get_practice(client, 9)
    await http.aclose()


@respx.mock
async def test_http_404_raises_tool_error(tmp_path):
    respx.get(f"{BASE}/practices").respond(404)
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="not found"):
        await api.get_practice(client, 9)
    await http.aclose()
