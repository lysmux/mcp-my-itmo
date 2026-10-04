from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import parse_optional_date, tool_errors
from mcp_my_itmo.features.sport import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_my_sport() -> dict:
        """My physical education summary: current sport semester, points (60+ from attendances means the credit is reached), sign-up attempts and debt."""
        summary = await api.get_my_sport(client)
        return summary.model_dump(exclude_none=True)

    @app.tool()
    @tool_errors
    async def list_sport_sections(
        date_from: str | None = None,
        date_to: str | None = None,
        building_id: int = 0,
        sport_type_ids: list[int] | None = None,
    ) -> list[dict]:
        """Sport lessons open for sign-up, by day: section, lesson_group_id, time, room, free places and whether signing in is allowed. Dates are ISO (YYYY-MM-DD); default window is today through 7 days. building_id 0 means all venues."""
        days = await api.list_sport_sections(
            client,
            parse_optional_date(date_from),
            parse_optional_date(date_to),
            building_id,
            sport_type_ids,
        )
        return [day.model_dump(exclude_none=True) for day in days]

    @app.tool()
    @tool_errors
    async def get_sport_schedule(
        date_from: str | None = None, date_to: str | None = None
    ) -> list[dict]:
        """My own sport lessons by day, past ones included. Dates are ISO (YYYY-MM-DD); default window is today through 7 days."""
        days = await api.get_sport_schedule(
            client, parse_optional_date(date_from), parse_optional_date(date_to)
        )
        return [day.model_dump(exclude_none=True) for day in days]

    @app.tool()
    @tool_errors
    async def enroll_sport_lessons(lesson_ids: list[int]) -> dict:
        """SIGNS THE USER UP FOR REAL SPORT LESSONS (free-visit lessons). Before calling, you MUST show the user the exact section, date and time of each lesson (see list_sport_sections) and get an explicit yes. The result echoes the lesson ids that were signed up."""
        signed = await api.enroll_lessons(client, lesson_ids)
        return {"enrolled": True, "requested_lesson_ids": lesson_ids, "result": signed}

    @app.tool()
    @tool_errors
    async def cancel_sport_lessons(lesson_ids: list[int]) -> dict:
        """CANCELS REAL SPORT LESSON SIGN-UPS. Before calling, you MUST show the user the exact section, date and time of each lesson (see get_sport_schedule) and get an explicit yes. The result echoes the lesson ids that were cancelled."""
        cancelled = await api.cancel_lessons(client, lesson_ids)
        return {"cancelled": True, "requested_lesson_ids": lesson_ids, "result": cancelled}

    @app.tool()
    @tool_errors
    async def enroll_sport_group(lesson_group_id: int) -> dict:
        """SIGNS THE USER UP FOR A WHOLE SPORT LESSON GROUP (a section's regular schedule). Before calling, you MUST confirm the exact section, group and weekly times with the user (see list_sport_sections) and get an explicit yes. Open classes of selective sections need a questionnaire and are not supported. The result echoes the group id."""
        await api.enroll_group(client, lesson_group_id)
        return {"enrolled": True, "lesson_group_id": lesson_group_id}

    @app.tool()
    @tool_errors
    async def cancel_sport_group(lesson_group_id: int) -> dict:
        """CANCELS A REAL SPORT LESSON GROUP SIGN-UP. Before calling, you MUST show the user the exact section and times and get an explicit yes. The result echoes the group id."""
        await api.cancel_group(client, lesson_group_id)
        return {"cancelled": True, "lesson_group_id": lesson_group_id}
