import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.personalities import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "personalities"
BASE = "https://my.itmo.ru/api/personalities/persons"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_search_sends_query_and_limit_and_parses_nulls(tmp_path):
    route = respx.get(BASE).respond(json=fixture("search.json"))
    client, http = await build_client(tmp_path)

    people = await api.search_people(client, "Testov", limit=5)
    await http.aclose()

    request = route.calls.last.request
    assert request.url.path == "/api/personalities/persons"
    assert request.url.params["q"] == "Testov"
    assert request.url.params["limit"] == "5"
    assert [person.id for person in people] == [100003, 100004]
    assert people[0].phone is None
    assert people[0].work == "Associate professor, Test Department"
    assert people[1].education == "Test Faculty, group A0000"
    assert people[1].work is None


@respx.mock
async def test_search_without_matches_returns_empty_list(tmp_path):
    respx.get(BASE).respond(json={"error_code": 0, "result": {"count": 0, "data": []}})
    client, http = await build_client(tmp_path)

    assert await api.search_people(client, "nobody") == []
    await http.aclose()


@respx.mock
async def test_search_with_null_result_returns_empty_list(tmp_path):
    respx.get(BASE).respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    assert await api.search_people(client, "nobody") == []
    await http.aclose()


async def test_blank_query_is_rejected(tmp_path):
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError):
        await api.search_people(client, "   ")
    await http.aclose()


@respx.mock
async def test_get_person_parses_card(tmp_path):
    route = respx.get(f"{BASE}/100003").respond(json=fixture("person.json"))
    client, http = await build_client(tmp_path)

    person = await api.get_person(client, 100003)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/personalities/persons/100003"
    assert person.isu == 100003
    assert person.contacts[0].contact == ["+7 000 000-00-00"]
    assert person.contacts[1].contact == []
    assert person.rooms[0].building_name == "Main building"
    assert [position.sorting for position in person.positions] == ["1", "2"]
    assert [position.on_vacation for position in person.positions] == [True, False]
    assert person.positions[1].start_vacation is None
    assert person.levels.rank is None and person.levels.degree == "PhD"
    assert person.powers[0].power_id == 5


@respx.mock
async def test_get_person_tolerates_sparse_card(tmp_path):
    respx.get(f"{BASE}/100004").respond(
        json={"result": {"isu": 100004, "fio": "Student", "levels": None, "powers": None, "positions": []}}
    )
    client, http = await build_client(tmp_path)

    person = await api.get_person(client, 100004)
    await http.aclose()

    assert person.levels is None
    assert person.powers == [] and person.contacts == []


@respx.mock
async def test_get_person_not_found_raises_tool_error(tmp_path):
    respx.get(f"{BASE}/1").respond(404, json={})
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="not found"):
        await api.get_person(client, 1)
    await http.aclose()


@respx.mock
async def test_get_person_with_empty_result_is_not_found(tmp_path):
    respx.get(f"{BASE}/1").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="not found"):
        await api.get_person(client, 1)
    await http.aclose()
