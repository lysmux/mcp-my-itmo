from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.requests import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def list_request_types() -> list[dict]:
        """Request/certificate types a student can create (type_id = id), with category."""
        types = await api.list_request_types(client)
        return [item.model_dump(exclude_none=True) for item in types]

    @app.tool()
    @tool_errors
    async def get_request_form(type_id: int) -> dict:
        """Form of a request type: its fields (field_id, name, type, required) and whether it can be created now. Use before create_request."""
        form = await api.get_request_form(client, type_id)
        return form.model_dump(exclude_none=True)

    @app.tool()
    @tool_errors
    async def list_my_requests(status: str | None = None) -> list[dict]:
        """Own submitted requests with statuses. Optional status filter: in_progress, done or rejected."""
        requests = await api.list_my_requests(client, status)
        return [item.model_dump(exclude_none=True) for item in requests]

    @app.tool()
    @tool_errors
    async def get_request(request_id: int) -> dict:
        """Details of one own request: status, approval chain and entered fields."""
        detail = await api.get_request(client, request_id)
        return detail.model_dump(exclude_none=True)

    @app.tool()
    @tool_errors
    async def create_request(type_id: int, params: dict | None = None) -> dict:
        """SUBMITS A REAL REQUEST. Before calling, you MUST show the user the exact request type and every field value and get an explicit yes. Call get_request_form first: `params` maps form field ids to values and the allowed fields depend on the type (dates DD.MM.YYYY, dictionary fields take a dictionary item id). The result echoes what was submitted and the new request id."""
        request_id = await api.create_request(client, type_id, params or {})
        return {
            "created": True,
            "request_id": request_id,
            "requested": {"type_id": type_id, "params": params or {}},
        }

    @app.tool()
    @tool_errors
    async def list_queues() -> list[dict]:
        """Electronic queues available to join; `my_entries` lists own sign-ups (application_id, date) in each queue."""
        queues = await api.list_queues(client)
        return [queue.model_dump(exclude_none=True) for queue in queues]

    @app.tool()
    @tool_errors
    async def get_queue(queue_id: int) -> dict:
        """One queue (queue_id = table_id) with its free `slots` (time_table_id, date) and own sign-ups."""
        queue = await api.get_queue(client, queue_id)
        return queue.model_dump(exclude_none=True)

    @app.tool()
    @tool_errors
    async def join_queue(
        queue_id: int,
        time_table_id: int,
        phone: str,
        comment: str | None = None,
        request_id: int | None = None,
    ) -> dict:
        """SIGNS THE USER UP FOR A REAL QUEUE SLOT. Before calling, you MUST confirm the exact queue, slot (time_table_id and its date from get_queue) and phone (at least 11 digits) with the user and get an explicit yes. Pass request_id only when the queue has a template_id (a request form must be submitted first). The result echoes the sign-up."""
        await api.join_queue(client, queue_id, time_table_id, phone, comment, request_id)
        return {
            "joined": True,
            "requested": {
                "queue_id": queue_id,
                "time_table_id": time_table_id,
                "phone": phone,
                "comment": comment,
                "request_id": request_id,
            },
        }

    @app.tool()
    @tool_errors
    async def leave_queue(application_id: int) -> dict:
        """CANCELS A REAL QUEUE SIGN-UP. Before calling, you MUST show the user the exact sign-up (queue and date; application_id from list_queues my_entries) and get an explicit yes. The result echoes the application id that was cancelled."""
        await api.leave_queue(client, application_id)
        return {"left": True, "application_id": application_id}
