import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.checklist import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "checklist"
URL = "https://my.itmo.ru/api/services/checklist/bypass"


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_bypass_parses_student_and_departments(tmp_path):
    route = respx.get(URL).respond(json=json.loads((FIXTURES / "bypass.json").read_text()))
    client, http = await build_client(tmp_path)

    sheet = await api.get_bypass(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/services/checklist/bypass"
    assert sheet.student[0].decision_id == 1
    assert sheet.student[0].comment is None
    assert sheet.departments[0].actions[0].action_id == 5
    assert sheet.departments[1].actions == []
    assert sheet.departments[1].problem is None


@respx.mock
async def test_null_result_gives_empty_sheet(tmp_path):
    respx.get(URL).respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    sheet = await api.get_bypass(client)
    await http.aclose()

    assert sheet.student == [] and sheet.departments == []


@respx.mock
async def test_error_code_raises_tool_error(tmp_path):
    respx.get(URL).respond(json={"error_code": 3, "error_message": "nope"})
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="nope"):
        await api.get_bypass(client)
    await http.aclose()
