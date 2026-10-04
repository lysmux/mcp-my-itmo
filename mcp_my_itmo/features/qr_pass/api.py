from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.qr_pass.models import QrPass

# Per go-itmo (myitmo/qr.go): qr.itmo.su takes the MyITMO access token and answers
# {"response": {"qr_hex": ...}}. Whether the token scope covers this host is unverified;
# live-verify pending.
PASS_URL = "https://qr.itmo.su/v1/user/pass"


async def get_pass(client: MyItmoClient) -> QrPass:
    body = await client.get_url(PASS_URL)
    raw = (body or {}).get("response")
    if not raw:
        raise ToolError("The pass service returned no pass.")
    return QrPass.model_validate(raw)
