import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.finances import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "finances"
BASE = "https://my.itmo.ru/api/finances"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_scholarship_account_parses_and_tolerates_null_dates(tmp_path):
    route = respx.get(f"{BASE}/scholarship/account").respond(json=fixture("scholarship_account.json"))
    client, http = await build_client(tmp_path)

    accounts = await api.get_scholarship_accounts(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/finances/scholarship/account"
    assert accounts[0].sum == 12000.5
    assert [item.item_name for item in accounts[0].payment_items] == ["State academic scholarship", "Bonus"]
    assert accounts[0].payment_items[1].date_end is None


@respx.mock
async def test_scholarship_income_tolerates_null_payment_and_account(tmp_path):
    route = respx.get(f"{BASE}/scholarship/income").respond(json=fixture("scholarship_income.json"))
    client, http = await build_client(tmp_path)

    months = await api.get_scholarship_income(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/finances/scholarship/income"
    assert months[0].payment.income[0].account is None
    assert months[0].payment.income_details[0].sum == 12000.5
    assert months[1].payment.income == []


@respx.mock
async def test_scholarship_totals_send_date_range_and_clean_names(tmp_path):
    route = respx.get(f"{BASE}/scholarship/total").respond(json=fixture("scholarship_total.json"))
    client, http = await build_client(tmp_path)

    totals = await api.get_scholarship_totals(client, "2026-01-01", "2026-06-30")
    await http.aclose()

    request = route.calls.last.request
    assert request.url.params["dateFrom"] == "2026-01-01"
    assert request.url.params["dateTo"] == "2026-06-30"
    assert totals[0].category_name == "Scholarship"
    assert totals[0].sum == 48000.0


@respx.mock
async def test_scholarship_totals_omit_unset_dates(tmp_path):
    route = respx.get(f"{BASE}/scholarship/total").respond(json=fixture("scholarship_total.json"))
    client, http = await build_client(tmp_path)

    await api.get_scholarship_totals(client)
    await http.aclose()

    assert dict(route.calls.last.request.url.params) == {}


@respx.mock
async def test_edu_contracts_accept_flexible_scalars(tmp_path):
    route = respx.get(f"{BASE}/edupayments/contracts").respond(json=fixture("edu_contracts.json"))
    client, http = await build_client(tmp_path)

    contracts = await api.get_edu_contracts(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/finances/edupayments/contracts"
    current, archived = contracts
    assert (current.contract_id, current.active, current.sum) == ("1001", True, 150000.5)
    assert (archived.contract_id, archived.number, archived.sum) == ("999", None, None)


@respx.mock
async def test_edu_payments_parse_schedule_and_null_installments(tmp_path):
    route = respx.get(f"{BASE}/edupayments/payments").respond(json=fixture("edu_payments.json"))
    client, http = await build_client(tmp_path)

    contracts = await api.get_edu_payments(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/finances/edupayments/payments"
    first, second = contracts
    assert first.payments[0].paid == 100000.0
    assert first.payments[0].pay_until == "2026-10-15"
    assert first.payments[1].paid is None
    assert second.payments == []


@respx.mock
async def test_empty_result_yields_empty_list(tmp_path):
    respx.get(f"{BASE}/scholarship/account").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    assert await api.get_scholarship_accounts(client) == []
    await http.aclose()


async def test_invalid_date_range_is_a_tool_error(tmp_path):
    client, http = await build_client(tmp_path)

    with pytest.raises(ToolError):
        await api.get_scholarship_totals(client, "not-a-date")
    await http.aclose()
