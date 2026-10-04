import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.record_book.api import RecordBookSelectionError
from mcp_my_itmo.config import Settings
from mcp_my_itmo.features.record_book import api
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures"
SPECIALIZATIONS_URL = "https://my.itmo.ru/api/record_book/specializations"
SEMESTER_5_URL = "https://my.itmo.ru/api/record_book/88681/5"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def build_client(tmp_path):
    from mcp_my_itmo.auth.store import TokenStore

    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    return MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http), http


@respx.mock
async def test_specializations_parse_with_semesters(tmp_path):
    respx.get(SPECIALIZATIONS_URL).respond(json=fixture("record_book_specializations.json"))
    client, http = await build_client(tmp_path)

    specializations = await api.list_specializations(client)
    await http.aclose()

    assert len(specializations) == 1
    assert specializations[0].main_plan == 88681
    assert specializations[0].specialization_name == "Программная инженерия"
    assert [(s.semester, s.actual) for s in specializations[0].semesters] == [(5, True), (6, False)]


@respx.mock
async def test_semester_parses_subjects_tolerating_nulls(tmp_path):
    respx.get(SEMESTER_5_URL).respond(json=fixture("record_book_semester.json"))
    client, http = await build_client(tmp_path)

    marks = await api.get_record_book(client, 88681, 5)
    await http.aclose()

    graded, ungraded = marks
    assert graded.name == "Операционные системы"
    assert graded.control_type == "Экзамен"
    assert graded.current_score == 85
    assert graded.teacher.surname == "Иванов"
    assert ungraded.current_score is None
    assert ungraded.rate is None
    assert ungraded.exam_date is None
    assert ungraded.teacher is None


@respx.mock
async def test_defaults_to_single_specialization_and_actual_semester(tmp_path):
    respx.get(SPECIALIZATIONS_URL).respond(json=fixture("record_book_specializations.json"))
    semester_route = respx.get(SEMESTER_5_URL).respond(json=fixture("record_book_semester.json"))
    client, http = await build_client(tmp_path)

    marks = await api.get_record_book(client)
    await http.aclose()

    assert semester_route.calls.last.request.url.path == "/api/record_book/88681/5"
    assert len(marks) == 2


@respx.mock
async def test_default_semester_falls_back_to_latest_when_none_actual(tmp_path):
    payload = fixture("record_book_specializations.json")
    for semester in payload["result"][0]["semesters"]:
        semester["actual"] = False
    respx.get(SPECIALIZATIONS_URL).respond(json=payload)
    route = respx.get("https://my.itmo.ru/api/record_book/88681/6").respond(
        json=fixture("record_book_semester.json")
    )
    client, http = await build_client(tmp_path)

    await api.get_record_book(client)
    await http.aclose()

    assert route.called


@respx.mock
async def test_unknown_specialization_is_reported(tmp_path):
    respx.get(SPECIALIZATIONS_URL).respond(json=fixture("record_book_specializations.json"))
    client, http = await build_client(tmp_path)

    with pytest.raises(RecordBookSelectionError):
        await api.get_record_book(client, specialization_id=1)
    await http.aclose()
