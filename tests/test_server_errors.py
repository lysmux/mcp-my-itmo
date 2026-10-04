import httpx
import pytest
from pydantic import ValidationError
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo import server
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import AuthRequired
from mcp_my_itmo.features.record_book import api as record_book_api
from mcp_my_itmo.features.record_book.models import SubjectMark
from mcp_my_itmo.features.timetable import api as timetable_api


def tool(name: str, app=None):
    return (app or server.create_app())._tool_manager.get_tool(name).fn


async def test_auth_required_becomes_login_hint(monkeypatch):
    async def raise_auth(*_args):
        raise AuthRequired("not logged in")

    monkeypatch.setattr(timetable_api, "get_schedule", raise_auth)

    with pytest.raises(ToolError, match="Run the `login` tool first"):
        await tool("get_schedule")()


async def test_malformed_date_becomes_friendly_message():
    with pytest.raises(ToolError, match="Invalid date; use YYYY-MM-DD"):
        await tool("get_schedule")(date_start="31/12/2026")


async def test_validation_error_becomes_informative_tool_error(monkeypatch):
    async def malformed_payload(*_args):
        SubjectMark.model_validate({"attempt": "not-a-number"})

    monkeypatch.setattr(timetable_api, "get_schedule", malformed_payload)

    with pytest.raises(ToolError, match="response shape changed") as info:
        await tool("get_schedule")()
    assert "Invalid date" not in str(info.value)


async def test_http_status_error_includes_status_path_and_server_message(monkeypatch):
    request = httpx.Request("GET", "https://my.itmo.ru/api/x/y?token=secret")
    response = httpx.Response(
        404, json={"error_message": "Nothing here"}, request=request
    )

    async def not_found(*_args):
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(timetable_api, "get_schedule", not_found)

    with pytest.raises(ToolError) as info:
        await tool("get_schedule")()
    message = str(info.value)
    assert "404" in message
    assert "/api/x/y" in message
    assert "Nothing here" in message
    assert "secret" not in message


async def test_http_status_error_with_plain_body_uses_snippet(monkeypatch):
    request = httpx.Request("GET", "https://my.itmo.ru/api/z")
    response = httpx.Response(502, text="Bad gateway page", request=request)

    async def bad_gateway(*_args):
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(timetable_api, "get_schedule", bad_gateway)

    with pytest.raises(ToolError, match="HTTP 502.*Bad gateway page"):
        await tool("get_schedule")()


async def test_connection_error_becomes_unreachable_message(monkeypatch):
    async def down(*_args):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(timetable_api, "get_schedule", down)

    with pytest.raises(ToolError, match="Could not reach my.itmo.ru: ConnectError"):
        await tool("get_schedule")()


async def test_domain_tool_error_passes_through_unchanged(monkeypatch):
    async def domain(*_args):
        raise ToolError("Domain problem")

    monkeypatch.setattr(timetable_api, "get_schedule", domain)

    with pytest.raises(ToolError) as info:
        await tool("get_schedule")()
    assert str(info.value) == "Domain problem"


async def test_unexpected_exception_becomes_tool_error(monkeypatch):
    async def boom(*_args):
        raise ValueError("not about dates")

    monkeypatch.setattr(record_book_api, "list_specializations", boom)

    with pytest.raises(ToolError, match="Unexpected error: ValueError: not about dates"):
        await tool("list_specializations")()


async def test_malformed_day_in_search_rooms_is_friendly():
    with pytest.raises(ToolError, match="Invalid date; use YYYY-MM-DD"):
        await tool("search_rooms")(1, "nope")


async def test_auth_status_unauthenticated_without_tokens(tmp_path):
    app = server.create_app(Settings(token_path=tmp_path / "tokens.json"))
    assert await tool("auth_status", app)() == {"authenticated": False}
