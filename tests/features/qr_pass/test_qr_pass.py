import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.qr_pass import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "qr_pass"
URL = "https://qr.itmo.su/v1/user/pass"


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_pass_unwraps_response_and_sends_bearer(tmp_path):
    route = respx.get(URL).respond(json=json.loads((FIXTURES / "pass.json").read_text()))
    client, http = await build_client(tmp_path)

    qr_pass = await api.get_pass(client)
    await http.aclose()

    assert qr_pass.qr_hex == "0a1b2c3d"
    assert route.calls.last.request.headers["Authorization"] == "Bearer access-1"


@respx.mock
async def test_missing_response_raises_tool_error(tmp_path):
    respx.get(URL).respond(json={"response": None})
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError):
        await api.get_pass(client)
    await http.aclose()
