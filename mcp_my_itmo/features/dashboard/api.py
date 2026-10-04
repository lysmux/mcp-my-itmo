from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import checked_result
from mcp_my_itmo.features.dashboard.models import DashboardWidget, MenuItem

# Routes per go-itmo (myitmo/system.go, base /api/system), live-verify pending.
# News is not served under /api/system in go-itmo, so no news tool is exposed.


async def get_dashboard(client: MyItmoClient) -> list[DashboardWidget]:
    result = checked_result(await client.get("/system/dashboard"))
    return [DashboardWidget.model_validate(item) for item in result or []]


async def get_menu(client: MyItmoClient) -> list[MenuItem]:
    result = checked_result(await client.get("/system/v1/menu/items"))
    return [MenuItem.model_validate(item) for item in (result or {}).get("menu") or []]
