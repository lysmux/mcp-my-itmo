from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.study_plan import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def list_study_plans() -> list[dict]:
        """Study plans (programmes) available to the student; `plan_id` feeds get_study_plan, `is_active` marks the current one."""
        programs = await api.list_study_plans(client)
        return [program.model_dump() for program in programs]

    @app.tool()
    @tool_errors
    async def get_study_plan(semester: int | None = None, plan_id: int | None = None) -> dict:
        """Curriculum disciplines of one semester with credits, hours per activity and control type (exam/credit). Omit both for the current semester of the active plan."""
        try:
            view = await api.get_study_plan(client, semester, plan_id)
        except api.StudyPlanSelectionError as error:
            raise ToolError(str(error)) from error
        return view.model_dump()
