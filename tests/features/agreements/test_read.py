import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.features.agreements import api
from mcp_my_itmo.features.agreements.models import Agreement
from tests.features.agreements.conftest import load_fixture

LIST_URL = "https://my.itmo.ru/api/agreements/agreements"


def test_model_parses_mixed_id_types_and_latest_version():
    agreements = [Agreement.model_validate(raw) for raw in load_fixture("agreements.json")["result"]]
    assert [a.id for a in agreements] == ["11", "12"]
    assert agreements[0].versions[1].id == "102"
    assert agreements[0].versions[1].status_id == 1
    assert agreements[0].latest_version().id == "102"


def test_model_tolerates_null_versions():
    agreement = Agreement.model_validate({"id": 1, "title": None, "versions": None})
    assert agreement.versions == []
    assert agreement.latest_version() is None


@respx.mock
async def test_list_agreements_unwraps_result_and_hits_path(client):
    route = respx.get(LIST_URL).respond(json=load_fixture("agreements.json"))
    agreements = await api.list_agreements(client)
    assert route.called
    assert [a.title for a in agreements] == ["Consent to personal data processing", "Dormitory rules"]


@respx.mock
async def test_list_agreements_empty_and_null_result(client):
    respx.get(LIST_URL).respond(json={"error_code": 0, "result": []})
    assert await api.list_agreements(client) == []
    respx.get(LIST_URL).respond(json={"error_code": 0, "result": None})
    assert await api.list_agreements(client) == []


@respx.mock
async def test_list_agreements_error_code_raises_tool_error(client):
    respx.get(LIST_URL).respond(json={"error_code": 5, "error_message": "Nope", "result": None})
    with pytest.raises(ToolError, match="Nope"):
        await api.list_agreements(client)


@respx.mock
async def test_list_agreements_http_error_raises_tool_error(client):
    respx.get(LIST_URL).respond(403)
    with pytest.raises(ToolError, match="403"):
        await api.list_agreements(client)
