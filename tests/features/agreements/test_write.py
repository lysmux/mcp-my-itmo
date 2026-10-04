import json

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.features.agreements import api
from tests.features.agreements.conftest import load_fixture

SIGN_URL = "https://my.itmo.ru/api/agreements/agreements/11/sign"


@respx.mock
async def test_accept_posts_empty_body_to_sign_path_and_returns_task(client):
    route = respx.post(SIGN_URL).respond(json=load_fixture("sign_task.json"))
    task = await api.accept_agreement(client, "11")
    assert route.calls.last.request.method == "POST"
    assert json.loads(route.calls.last.request.content) == {}
    assert task.task_id == "task-1"
    assert task.signature_id == "sig-1"


@respx.mock
async def test_accept_sends_unique_idempotency_key(client):
    route = respx.post(SIGN_URL).respond(json=load_fixture("sign_task.json"))
    await api.accept_agreement(client, "11")
    await api.accept_agreement(client, "11")
    keys = [call.request.headers["Idempotency-Key"] for call in route.calls]
    assert all(keys)
    assert keys[0] != keys[1]


@respx.mock
async def test_accept_server_rejection_raises_tool_error(client):
    respx.post(SIGN_URL).respond(json={"error_code": 9, "error_message": "Already signed", "result": None})
    with pytest.raises(ToolError, match="Already signed"):
        await api.accept_agreement(client, "11")


@respx.mock
async def test_accept_http_error_raises_tool_error(client):
    respx.post(SIGN_URL).respond(500)
    with pytest.raises(ToolError, match="500"):
        await api.accept_agreement(client, "11")


@respx.mock
async def test_accept_rejects_blank_id_without_request(client):
    with pytest.raises(ToolError):
        await api.accept_agreement(client, " ")


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text=""),
        httpx.Response(200, text="<html></html>"),
        httpx.Response(200, json=["x"]),
        httpx.Response(200, json={"error_code": 0, "result": None}),
        httpx.Response(200, json={"error_code": 0, "result": {}}),
    ],
)
async def test_accept_without_sign_task_evidence_raises(client, response):
    respx.post(SIGN_URL).mock(return_value=response)
    with pytest.raises(ToolError, match="Could not confirm"):
        await api.accept_agreement(client, "11")
