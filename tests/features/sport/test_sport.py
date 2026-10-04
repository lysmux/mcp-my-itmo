import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.sport import api
from mcp_my_itmo.features.sport.models import SportScheduleDay, SportScore
from tests.core.test_client import FakeAuth, make_tokens

BASE = "https://my.itmo.ru/api/sport"
FIXTURES = Path(__file__).parents[2] / "fixtures" / "sport"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_get_my_sport_combines_semester_score_attempts_debt(tmp_path):
    respx.get(f"{BASE}/semesters/current").respond(json=fixture("semester_current.json"))
    score_route = respx.get(f"{BASE}/personal/score").respond(json=fixture("score.json"))
    respx.get(f"{BASE}/personal/have_attempts").respond(json=fixture("attempts.json"))
    respx.get(f"{BASE}/personal/debt").respond(json=fixture("debt.json"))
    client, http = await build_client(tmp_path)
    summary = await api.get_my_sport(client)
    await http.aclose()
    assert score_route.calls.last.request.url.params["semester_id"] == "42"
    assert summary.semester.study_year == "2026/2027"
    assert summary.score.sum.attendances == 45
    assert summary.attempts.free_attempts == 1
    assert summary.debt.is_having_debt is False


@respx.mock
async def test_get_my_sport_tolerates_null_results(tmp_path):
    respx.get(f"{BASE}/semesters/current").respond(json={"error_code": 0, "result": None})
    respx.get(f"{BASE}/personal/have_attempts").respond(json={"error_code": 0, "result": None})
    respx.get(f"{BASE}/personal/debt").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)
    summary = await api.get_my_sport(client)
    await http.aclose()
    assert summary.semester is None and summary.score is None


@respx.mock
async def test_read_error_code_becomes_tool_error(tmp_path):
    respx.get(f"{BASE}/semesters/current").respond(
        json={"error_code": 114, "error_message": "No access", "result": None}
    )
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="No access"):
        await api.get_my_sport(client)
    await http.aclose()


@respx.mock
async def test_list_sport_sections_sends_params_and_tolerates_null_lessons(tmp_path):
    route = respx.get(f"{BASE}/sign/schedule").respond(json=fixture("schedule.json"))
    client, http = await build_client(tmp_path)
    days = await api.list_sport_sections(
        client, date(2026, 10, 6), date(2026, 10, 12), sport_type_ids=[3]
    )
    await http.aclose()
    params = route.calls.last.request.url.params
    assert params["date_start"] == "2026-10-06"
    assert params["date_end"] == "2026-10-12"
    assert params["building_id"] == "0"
    assert params["sport_type_id"] == "3"
    assert days[0].lessons[0].lesson_group_id == 300
    assert days[0].lessons[0].can_sign_in.unavailable_reasons == ["Already chosen"]
    assert days[1].lessons == []


@respx.mock
async def test_get_sport_schedule_uses_personal_calendar(tmp_path):
    route = respx.get(f"{BASE}/personal/calendar").respond(json=fixture("calendar.json"))
    client, http = await build_client(tmp_path)
    days = await api.get_sport_schedule(client, date(2026, 10, 6), date(2026, 10, 7))
    await http.aclose()
    assert route.calls.last.request.url.params["date_start"] == "2026-10-06"
    assert days[0].lessons[0].signed is True


@respx.mock
async def test_empty_result_gives_empty_list(tmp_path):
    respx.get(f"{BASE}/personal/calendar").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)
    assert await api.get_sport_schedule(client, date(2026, 10, 6)) == []
    await http.aclose()


async def test_reversed_window_is_tool_error(tmp_path):
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError):
        await api.get_sport_schedule(client, date(2026, 10, 7), date(2026, 10, 6))
    await http.aclose()


def test_models_tolerate_nulls():
    assert SportScore.model_validate({"sum": None, "attendances": None}).attendances == []
    assert SportScheduleDay.model_validate({"date": None, "lessons": None}).lessons == []


@respx.mock
async def test_enroll_lessons_posts_id_array(tmp_path):
    route = respx.post(f"{BASE}/sign/schedule/lessons").respond(
        json={"error_code": 0, "result": [9001]}
    )
    client, http = await build_client(tmp_path)
    result = await api.enroll_lessons(client, [9001])
    await http.aclose()
    assert json.loads(route.calls.last.request.content) == [9001]
    assert result == [9001]


@respx.mock
async def test_cancel_lessons_deletes_with_id_array(tmp_path):
    route = respx.delete(f"{BASE}/sign/schedule/lessons").respond(
        json={"error_code": 0, "result": [9001]}
    )
    client, http = await build_client(tmp_path)
    await api.cancel_lessons(client, [9001])
    await http.aclose()
    assert json.loads(route.calls.last.request.content) == [9001]


@respx.mock
async def test_enroll_and_cancel_group_paths(tmp_path):
    post = respx.post(f"{BASE}/sign/schedule/lesson_groups/300").respond(
        json={"error_code": 0, "result": None}
    )
    delete = respx.delete(f"{BASE}/sign/schedule/lesson_groups/300").respond(
        json={"error_code": 0, "result": None}
    )
    client, http = await build_client(tmp_path)
    await api.enroll_group(client, 300)
    await api.cancel_group(client, 300)
    await http.aclose()
    assert post.called and delete.called


@respx.mock
async def test_server_rejection_becomes_tool_error(tmp_path):
    respx.post(f"{BASE}/sign/schedule/lessons").respond(
        json={"error_code": 137, "error_message": "Already chosen today", "result": None}
    )
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="Already chosen today"):
        await api.enroll_lessons(client, [9001])
    await http.aclose()


@respx.mock
async def test_http_error_on_cancel_becomes_tool_error(tmp_path):
    respx.delete(f"{BASE}/sign/schedule/lesson_groups/300").respond(500, text="boom")
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="HTTP 500"):
        await api.cancel_group(client, 300)
    await http.aclose()


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text=""),
        httpx.Response(200, text="<html></html>"),
        httpx.Response(200, json=[9001]),
    ],
)
async def test_sport_write_without_json_object_raises(tmp_path, response):
    respx.post(f"{BASE}/sign/schedule/lessons").mock(return_value=response)
    client, http = await build_client(tmp_path)
    with pytest.raises(ToolError, match="Could not confirm"):
        await api.enroll_lessons(client, [9001])
    await http.aclose()
