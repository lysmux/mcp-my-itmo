from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import parse_date, parse_optional_date, tool_errors
from mcp_my_itmo.features.booking import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def list_room_groups() -> list[dict]:
        """Room booking groups (top of the catalogue); use group_id with list_room_categories."""
        return [group.model_dump() for group in await api.list_room_groups(client)]

    @app.tool()
    @tool_errors
    async def list_room_categories(group_id: int) -> list[dict]:
        """Room categories inside a group; use category_id with list_rooms_in_category or search_rooms."""
        categories = await api.list_room_categories(client, group_id)
        return [category.model_dump() for category in categories]

    @app.tool()
    @tool_errors
    async def list_rooms_in_category(category_id: int) -> list[dict]:
        """Rooms of a category with capacity, address and equipment."""
        rooms = await api.list_rooms_in_category(client, category_id)
        return [room.model_dump(exclude_none=True) for room in rooms]

    @app.tool()
    @tool_errors
    async def search_rooms(category_id: int, day: str) -> list[dict]:
        """Room availability for a day (YYYY-MM-DD): each room lists its already-booked `busy` intervals; time outside them is free."""
        rooms = await api.search_rooms(client, category_id, parse_date(day))
        return [room.model_dump(exclude_none=True) for room in rooms]

    @app.tool()
    @tool_errors
    async def list_my_bookings(
        date_start: str | None = None, date_end: str | None = None
    ) -> list[dict]:
        """Own room bookings. Dates are ISO (YYYY-MM-DD); default window is today through the next 60 days."""
        bookings = await api.list_my_bookings(
            client,
            parse_optional_date(date_start),
            parse_optional_date(date_end),
        )
        return [booking.model_dump(exclude_none=True) for booking in bookings]

    @app.tool()
    @tool_errors
    async def create_booking(
        room_id: int,
        day: str,
        time_from: str,
        time_to: str,
        name: str | None = None,
        participants: int = 1,
        contact_phone: str | None = None,
    ) -> dict:
        """CREATES A REAL ROOM BOOKING. Before calling, you MUST confirm the exact room, date (YYYY-MM-DD) and time range (HH:MM) with the user and get an explicit yes; never guess or book speculatively. Use search_rooms first to check the slot is free. The server returns no content on success, so the result echoes the exact booking that was requested."""
        booking = await api.create_booking(
            client, room_id, parse_date(day), time_from, time_to, name, participants, contact_phone
        )
        return {
            "created": True,
            "requested": {
                "room_id": room_id,
                "date": day,
                "time_from": time_from,
                "time_to": time_to,
            },
            "booking": booking,
        }

    @app.tool()
    @tool_errors
    async def cancel_booking(booking_id: int) -> dict:
        """CANCELS A REAL ROOM BOOKING. Before calling, you MUST show the user the exact booking (room, date, time; see list_my_bookings) and get an explicit yes. The result echoes the booking id that was cancelled."""
        await api.cancel_booking(client, booking_id)
        return {"cancelled": True, "booking_id": booking_id}
