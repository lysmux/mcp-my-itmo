from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import checked_result
from mcp_my_itmo.features.checklist.models import ChecklistBypass

# Route per go-itmo (myitmo/checklist.go), live-verify pending.
# decision_id: 1 = problem or debt, 2 = warning, 3 = cleared.


async def get_bypass(client: MyItmoClient) -> ChecklistBypass:
    result = checked_result(await client.get("/services/checklist/bypass"))
    return ChecklistBypass.model_validate(result or {})
