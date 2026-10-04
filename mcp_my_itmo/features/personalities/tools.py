from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.personalities import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def search_people(query: str, limit: int = api.DEFAULT_LIMIT) -> list[dict]:
        """Search the people directory (students, teachers, staff) by name or ISU number. Result id is the person_id for get_person."""
        people = await api.search_people(client, query, limit)
        return [person.model_dump() for person in people]

    @app.tool()
    @tool_errors
    async def get_person(person_id: int) -> dict:
        """Public card of a person by ISU number: contacts, rooms, positions, degrees, responsibilities."""
        person = await api.get_person(client, person_id)
        return person.model_dump()
