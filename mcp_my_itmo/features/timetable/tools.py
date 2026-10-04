from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import parse_optional_date, tool_errors
from mcp_my_itmo.features.timetable import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_schedule(date_start: str | None = None, date_end: str | None = None) -> dict:
        """Personal timetable grouped by day. Dates are ISO (YYYY-MM-DD); omit both for the current week."""
        week = await api.get_schedule(
            client,
            parse_optional_date(date_start),
            parse_optional_date(date_end),
        )
        return {
            "days": [
                {
                    "date": day.day.isoformat(),
                    "lessons": [lesson.model_dump(exclude_none=True) for lesson in day.lessons],
                }
                for day in week.days
            ]
        }
