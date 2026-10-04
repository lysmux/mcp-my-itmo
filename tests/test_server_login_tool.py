import asyncio

import httpx

from mcp_my_itmo import server
from mcp_my_itmo.auth.keycloak import KeycloakAuth
from mcp_my_itmo.auth.store import TokenSet, TokenStore
from mcp_my_itmo.config import Settings


def build_tool(name: str, token_path):
    app = server.create_app(Settings(token_path=token_path))
    return app._tool_manager.get_tool(name).fn


async def test_login_returns_error_when_page_fails_to_start(monkeypatch, tmp_path):
    async def failing_page(*args, **kwargs):
        raise OSError("port in use")

    monkeypatch.setattr(server, "run_login_page", failing_page)
    login = build_tool("login", tmp_path / "tokens.json")

    async with asyncio.timeout(5):
        outcome = await login()

    assert "port in use" in outcome


async def test_logout_clears_store_even_if_remote_logout_fails(monkeypatch, tmp_path):
    token_path = tmp_path / "tokens.json"
    store = TokenStore(token_path)
    store.save(TokenSet("a", "r", None, 1e12, 1e12))

    async def failing_logout(self, refresh_token):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(KeycloakAuth, "logout", failing_logout)

    await build_tool("logout", token_path)()

    assert store.load() is None
