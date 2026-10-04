from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.profile.models import Profile


async def get_profile(client: MyItmoClient) -> Profile:
    claims = await client.get_url(client.userinfo_endpoint)
    return Profile.model_validate(claims)
