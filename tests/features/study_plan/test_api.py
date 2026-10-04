import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.study_plan import api
from mcp_my_itmo.features.study_plan.models import StudyPlan
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "study_plan"
BASE = "https://my.itmo.ru/api/eduPlanNew"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


def test_plan_model_parses_fixture_and_tolerates_null_contents():
    plan = StudyPlan.model_validate(fixture("plan.json")["result"])

    assert plan.current_semester == 5
    assert plan.plan_info.direction_code == "01.03.02"
    module = plan.structure[0].children[0]
    assert module.children[2].contents == {}
    assert module.children[0].contents["5"][0].activities[2].volume is None


@respx.mock
async def test_list_study_plans_unwraps_result(tmp_path):
    route = respx.get(f"{BASE}/programs").respond(json=fixture("programs.json"))
    client, http = await build_client(tmp_path)

    programs = await api.list_study_plans(client)
    await http.aclose()

    assert route.calls.last.request.url.path == "/api/eduPlanNew/programs"
    assert [p.plan_id for p in programs] == [400, 500]
    assert programs[1].specialization_id is None


@respx.mock
async def test_default_path_uses_active_program_and_current_semester(tmp_path):
    respx.get(f"{BASE}/programs").respond(json=fixture("programs.json"))
    plan_route = respx.get(f"{BASE}/study_plan/500").respond(json=fixture("plan.json"))
    client, http = await build_client(tmp_path)

    view = await api.get_study_plan(client)
    await http.aclose()

    request = plan_route.calls.last.request
    assert request.url.path == "/api/eduPlanNew/study_plan/500"
    assert "spec_id" not in request.url.params
    assert view.semester == 5
    assert view.total_credits == 3
    [discipline] = view.disciplines
    assert discipline.name == "Discipline A"
    assert discipline.module == "Block 1 / Module"
    assert discipline.credits == 3
    assert discipline.control_type == "exam"
    assert discipline.hours == 72
    assert [a.name for a in discipline.activities] == ["Lectures", "Self-study"]


@respx.mock
async def test_explicit_plan_and_semester_send_spec_id_and_skip_programs(tmp_path):
    programs = respx.get(f"{BASE}/programs").respond(json=fixture("programs.json"))
    plan_route = respx.get(f"{BASE}/study_plan/400").respond(json=fixture("plan.json"))
    client, http = await build_client(tmp_path)

    view = await api.get_study_plan(client, semester=6, plan_id=400)
    await http.aclose()

    assert programs.called
    assert plan_route.calls.last.request.url.params["spec_id"] == "3"
    assert [d.name for d in view.disciplines] == ["Discipline B"]
    assert view.disciplines[0].control_type == "credit"


@respx.mock
async def test_unknown_plan_id_raises_selection_error(tmp_path):
    respx.get(f"{BASE}/programs").respond(json=fixture("programs.json"))
    client, http = await build_client(tmp_path)

    with pytest.raises(api.StudyPlanSelectionError):
        await api.get_study_plan(client, plan_id=999)
    await http.aclose()


@respx.mock
async def test_no_programs_raises_selection_error(tmp_path):
    respx.get(f"{BASE}/programs").respond(json={"error_code": 0, "result": None})
    client, http = await build_client(tmp_path)

    with pytest.raises(api.StudyPlanSelectionError):
        await api.get_study_plan(client)
    await http.aclose()


@respx.mock
async def test_empty_structure_gives_empty_view(tmp_path):
    respx.get(f"{BASE}/programs").respond(json=fixture("programs.json"))
    respx.get(f"{BASE}/study_plan/500").respond(json={"error_code": 0, "result": {"id": 500}})
    client, http = await build_client(tmp_path)

    view = await api.get_study_plan(client)
    await http.aclose()

    assert view.disciplines == []
    assert view.semester is None
