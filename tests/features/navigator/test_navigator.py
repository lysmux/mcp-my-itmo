import json
from pathlib import Path

import httpx
import respx

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.navigator import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "navigator"
URL = "https://my.itmo.ru/api/navigator/buildings"


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_buildings_parse_without_envelope_and_tolerate_null_bounds(tmp_path):
    route = respx.get(URL).respond(json=json.loads((FIXTURES / "buildings.json").read_text()))
    client, http = await build_client(tmp_path)

    buildings = await api.search_buildings(client, "")
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/navigator/buildings"
    assert [b.building_id for b in buildings] == [1, 2]
    assert buildings[0].bounds == [30.31, 59.95, 30.32, 59.96]
    assert buildings[1].bounds is None


@respx.mock
async def test_search_filters_by_name_case_insensitively(tmp_path):
    respx.get(URL).respond(json=json.loads((FIXTURES / "buildings.json").read_text()))
    client, http = await build_client(tmp_path)

    found = await api.search_buildings(client, "KRONV")
    await http.aclose()

    assert [b.name for b in found] == ["Kronverksky 49"]


@respx.mock
async def test_null_body_yields_empty_list(tmp_path):
    respx.get(URL).respond(content=b"null")
    client, http = await build_client(tmp_path)

    assert await api.search_buildings(client, "x") == []
    await http.aclose()
