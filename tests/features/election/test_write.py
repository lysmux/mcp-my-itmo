import json

import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.features.election import api
from tests.features.election.conftest import load_fixture

INTRO = "https://my.itmo.ru/api/intro"
FACULTATIVE = "https://my.itmo.ru/api/facultative"


def sent_body(route):
    return json.loads(route.calls.last.request.content)


@respx.mock
async def test_choose_books_flow_with_selected_flows_body(client):
    route = respx.post(f"{FACULTATIVE}/booking/").respond(json=load_fixture("ok.json"))
    await api.choose_flow(client, "facultative", 7001)
    assert sent_body(route) == {"selected_flows": [7001], "canceled_flows": []}


@respx.mock
async def test_withdraw_books_flow_as_canceled(client):
    route = respx.post(f"{INTRO}/booking/").respond(json=load_fixture("ok.json"))
    await api.withdraw_flow(client, "intro", 7001)
    assert sent_body(route) == {"selected_flows": [], "canceled_flows": [7001]}


@respx.mock
async def test_choose_with_clashes_raises_tool_error_mentioning_clash(client):
    respx.post(f"{FACULTATIVE}/booking/").respond(json=load_fixture("elective_clashes.json"))
    with pytest.raises(ToolError, match="clash") as raised:
        await api.choose_flow(client, "facultative", 7001)
    assert "7002" in str(raised.value)


@respx.mock
async def test_choose_server_rejection_raises_tool_error(client):
    respx.post(f"{FACULTATIVE}/booking/").respond(
        json={"error_code": 7, "error_message": "No free places", "result": None}
    )
    with pytest.raises(ToolError, match="No free places"):
        await api.choose_flow(client, "facultative", 7001)


@respx.mock
async def test_choose_http_error_raises_tool_error(client):
    respx.post(f"{INTRO}/booking/").respond(500)
    with pytest.raises(ToolError):
        await api.choose_flow(client, "intro", 7001)


@respx.mock
async def test_confirm_commits_all_current_flows_with_confirm_status(client):
    respx.get(f"{FACULTATIVE}/current/").respond(json=load_fixture("elective_current.json"))
    route = respx.post(f"{FACULTATIVE}/commit/").respond(json=load_fixture("ok.json"))
    await api.confirm_choice(client, "facultative")
    assert sent_body(route) == {"status": 2, "flow_id": [7001]}


@respx.mock
async def test_confirm_rejection_raises_tool_error(client):
    respx.get(f"{FACULTATIVE}/current/").respond(json=load_fixture("elective_current.json"))
    respx.post(f"{FACULTATIVE}/commit/").respond(
        json={"error_code": 3, "error_message": "Required groups unsatisfied", "result": None}
    )
    with pytest.raises(ToolError, match="Required groups"):
        await api.confirm_choice(client, "facultative")


async def test_writes_reject_election_kind(client):
    with pytest.raises(ToolError):
        await api.choose_flow(client, "election", 1)
