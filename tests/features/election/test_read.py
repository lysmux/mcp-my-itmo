import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.features.election import api
from mcp_my_itmo.features.election.models import ElectionDiscipline, ElectiveNode
from tests.features.election.conftest import load_fixture

ELECTION = "https://my.itmo.ru/api/election/students"
INTRO = "https://my.itmo.ru/api/intro"
FACULTATIVE = "https://my.itmo.ru/api/facultative"


@respx.mock
async def test_election_offers_parse_disciplines_and_tolerate_nulls(client):
    route = respx.get(f"{ELECTION}/available_disciplines").respond(
        json=load_fixture("available_disciplines.json")
    )
    offers = await api.list_election_offers(client, "election")
    assert route.called
    assert isinstance(offers[0], ElectionDiscipline)
    assert offers[0].disc_name == "Machine Learning"
    assert offers[0].semesters[0].group_flow == "gf-501-1"
    assert offers[0].not_compatible_with == [502]
    assert offers[1].semesters == []
    assert offers[1].not_compatible_with == []


@respx.mock
@pytest.mark.parametrize("kind,base", [("intro", INTRO), ("facultative", FACULTATIVE)])
async def test_elective_offers_unwrap_json_tree(client, kind, base):
    route = respx.get(f"{base}/json/").respond(json=load_fixture("elective_tree.json"))
    offers = await api.list_election_offers(client, kind)
    assert route.called
    assert isinstance(offers[0], ElectiveNode)
    flow = offers[0].variants[0].variants[0]
    assert (flow.id, flow.work_type, flow.teachers) == (7001, 1, ["Petrov P.P."])
    assert flow.variants == []


@respx.mock
async def test_offers_empty_result_is_empty_list(client):
    respx.get(f"{FACULTATIVE}/json/").respond(
        json={"error_code": 0, "error_message": None, "result": None}
    )
    assert await api.list_election_offers(client, "facultative") == []


async def test_unknown_kind_is_tool_error(client):
    with pytest.raises(ToolError):
        await api.list_election_offers(client, "bogus")


@respx.mock
async def test_election_offers_error_envelope_raises_tool_error(client):
    respx.get(f"{ELECTION}/available_disciplines").respond(
        json={"error_code": 5, "error_message": "No access", "result": None}
    )
    with pytest.raises(ToolError, match="No access"):
        await api.list_election_offers(client, "election")


@respx.mock
async def test_my_elections_combines_all_flows(client):
    respx.get(f"{ELECTION}/availability").respond(json=load_fixture("availability.json"))
    respx.get(f"{ELECTION}/chosen_flows").respond(json=load_fixture("chosen_flows.json"))
    respx.get(f"{ELECTION}/ordered_flow_chains").respond(
        json=load_fixture("ordered_flow_chains.json")
    )
    for base in (INTRO, FACULTATIVE):
        respx.get(f"{base}/status/").respond(json=load_fixture("elective_status.json"))
        respx.get(f"{base}/current/").respond(json=load_fixture("elective_current.json"))
    mine = await api.get_my_elections(client)
    assert mine["election"]["availability"]["id"] == 1
    assert mine["election"]["chosen_flow_ids"] == [9001, 9002]
    assert mine["election"]["chains"][0]["flows"][0]["teachers"] == ["Ivanov I.I."]
    assert mine["facultative"]["current"]["flow_id"] == [7001]
    assert mine["intro"]["period"]["choice_status"] == 0


@respx.mock
async def test_my_elections_isolates_inaccessible_section(client):
    respx.get(f"{ELECTION}/availability").respond(404)
    respx.get(f"{ELECTION}/chosen_flows").respond(404)
    respx.get(f"{ELECTION}/ordered_flow_chains").respond(404)
    respx.get(f"{INTRO}/status/").respond(json=load_fixture("elective_status_empty.json"))
    respx.get(f"{INTRO}/current/").respond(json=load_fixture("elective_current.json"))
    respx.get(f"{FACULTATIVE}/status/").respond(403)
    respx.get(f"{FACULTATIVE}/current/").respond(403)
    mine = await api.get_my_elections(client)
    assert "unavailable" in mine["election"]["error"].lower()
    assert "unavailable" in mine["facultative"]["error"].lower()
    assert mine["intro"]["period"] is None
    assert mine["intro"]["current"]["flow_id"] == [7001]
