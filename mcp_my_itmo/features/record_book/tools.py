from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.record_book import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def list_specializations() -> list[dict]:
        """Study programs (specializations) with their semesters; `actual` marks the current semester."""
        specializations = await api.list_specializations(client)
        return [specialization.model_dump() for specialization in specializations]

    @app.tool()
    @tool_errors
    async def get_record_book(
        specialization_id: int | None = None, semester: int | None = None
    ) -> list[dict]:
        """Grades per subject. specialization_id is the main_plan from list_specializations; omit both for the current semester."""
        try:
            marks = await api.get_record_book(client, specialization_id, semester)
        except api.RecordBookSelectionError as error:
            raise ToolError(str(error)) from error
        return [mark.model_dump(exclude_none=True) for mark in marks]
