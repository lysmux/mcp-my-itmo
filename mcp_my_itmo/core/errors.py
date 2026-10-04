import functools
from datetime import date

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from pydantic import ValidationError

from mcp_my_itmo.core.client import AuthRequired

NOT_LOGGED_IN_MESSAGE = "Not logged in. Run the `login` tool first."
INVALID_DATE_MESSAGE = "Invalid date; use YYYY-MM-DD."
MAX_DETAIL_LENGTH = 200
MAX_REPORTED_FIELDS = 5


def _server_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("error_message", "message", "error"):
            if isinstance(body.get(key), str) and body[key]:
                return body[key][:MAX_DETAIL_LENGTH]
    return response.text.strip()[:MAX_DETAIL_LENGTH]


def _http_status_message(error: httpx.HTTPStatusError) -> str:
    response = error.response
    message = f"my.itmo.ru returned HTTP {response.status_code} for {error.request.url.path}"
    detail = _server_message(response)
    return f"{message}: {detail}" if detail else message


def _to_tool_error(error: Exception) -> ToolError:
    if isinstance(error, AuthRequired):
        return ToolError(NOT_LOGGED_IN_MESSAGE)
    if isinstance(error, httpx.HTTPStatusError):
        return ToolError(_http_status_message(error))
    if isinstance(error, httpx.HTTPError):
        return ToolError(f"Could not reach my.itmo.ru: {type(error).__name__}")
    if isinstance(error, ValidationError):
        fields = ", ".join(
            ".".join(str(part) for part in detail["loc"]) or "<root>"
            for detail in error.errors()[:MAX_REPORTED_FIELDS]
        )
        return ToolError(
            "Unexpected response from my.itmo.ru (response shape changed): "
            f"{error.error_count()} invalid field(s): {fields}"
        )
    return ToolError(f"Unexpected error: {type(error).__name__}: {error}")


def tool_errors(tool):
    """Map every failure of an async tool to an informative ToolError."""

    @functools.wraps(tool)
    async def wrapper(*args, **kwargs):
        try:
            return await tool(*args, **kwargs)
        except ToolError:
            raise
        except Exception as error:
            raise _to_tool_error(error) from error

    return wrapper


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ToolError(INVALID_DATE_MESSAGE) from error


def parse_optional_date(value: str | None) -> date | None:
    return parse_date(value) if value else None
