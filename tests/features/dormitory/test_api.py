import json
from pathlib import Path

import httpx
import respx
from mcp.server.fastmcp.exceptions import ToolError
import pytest

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.dormitory import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "dormitory"
BASE = "https://my.itmo.ru/api/dormitory"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_status_parses_assigned_dormitory_and_appointment(tmp_path):
    route = respx.get(f"{BASE}/status/full").respond(json=fixture("status.json"))
    client, http = await build_client(tmp_path)

    status = await api.get_status(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/dormitory/status/full"
    assert (status.status_id, status.dorm_type, status.queue_place) == (3, "dorm", None)
    assert status.assigned_dormitory.name == "Dormitory 1"
    assert status.assigned_dormitory.address == "1 Example St"
    assert status.appointment.time_slot == "2026-08-28T10:30:00+03:00"


@respx.mock
async def test_status_tolerates_null_sections(tmp_path):
    respx.get(f"{BASE}/status/full").respond(json=fixture("status_queued.json"))
    client, http = await build_client(tmp_path)

    status = await api.get_status(client)
    await http.aclose()

    assert status.queue_place == 17
    assert status.assigned_dormitory is None
    assert status.appointment is None


@respx.mock
async def test_status_is_none_without_settlement(tmp_path):
    respx.get(f"{BASE}/status/full").respond(json=fixture("status_none.json"))
    client, http = await build_client(tmp_path)

    assert await api.get_status(client) is None
    await http.aclose()


@respx.mock
async def test_status_error_code_raises_tool_error(tmp_path):
    respx.get(f"{BASE}/status/full").respond(
        json={"error_code": 5, "error_message": "Forbidden", "result": None}
    )
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="Forbidden"):
        await api.get_status(client)
    await http.aclose()


@respx.mock
async def test_payments_fetch_contracts_for_each_period(tmp_path):
    periods = respx.get(f"{BASE}/payments/contracts/periods").respond(json=fixture("periods.json"))
    contracts = respx.get(f"{BASE}/payments/contracts").respond(json=fixture("contracts.json"))
    client, http = await build_client(tmp_path)

    result = await api.get_payments(client)
    await http.aclose()

    assert periods.called
    assert contracts.call_count == 1
    params = contracts.calls.last.request.url.params
    assert (params["from"], params["to"]) == ("2026-01-01", "2026-12-31")
    assert [period.year for period in result] == [2026, 2025]
    first = result[0].contracts
    assert (first[0].contract_id, first[0].balance, first[0].payments[0].sum) == ("55", -4200.0, 4200.0)
    assert first[1].payments == []
    assert result[1].contracts == []


@respx.mock
async def test_payments_empty_without_periods(tmp_path):
    respx.get(f"{BASE}/payments/contracts/periods").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    assert await api.get_payments(client) == []
    await http.aclose()


@respx.mock
async def test_payments_error_code_raises_tool_error(tmp_path):
    respx.get(f"{BASE}/payments/contracts/periods").respond(
        json={"error_code": 9, "error_message": "No access", "result": None}
    )
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError, match="No access"):
        await api.get_payments(client)
    await http.aclose()
