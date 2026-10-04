import asyncio

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.auth.keycloak import KeycloakAuth
from mcp_my_itmo.auth.login_server import run_login_page
from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import AuthRequired, MyItmoClient
from mcp_my_itmo.features import (
    agreements,
    booking,
    checklist,
    dashboard,
    dormitory,
    election,
    navigator,
    qr_pass,
    requests,
    finances,
    personalities,
    practices,
    profile,
    record_book,
    sport,
    study_plan,
    timetable,
)

FEATURES = (
    timetable,
    record_book,
    requests,
    profile,
    booking,
    finances,
    study_plan,
    personalities,
    practices,
    sport,
    election,
    dormitory,
    agreements,
    navigator,
    dashboard,
    qr_pass,
    checklist,
)


def _register_auth(
    app: FastMCP,
    settings: Settings,
    http: httpx.AsyncClient,
    store: TokenStore,
    auth: KeycloakAuth,
    client: MyItmoClient,
) -> None:
    login_task: asyncio.Task | None = None

    @app.tool()
    async def login() -> str:
        """Start a local login page; the user enters credentials there, never in chat."""
        nonlocal login_task
        if login_task is not None and not login_task.done():
            return "A login page is already open. Finish signing in there, then call auth_status."
        ready: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        login_task = asyncio.create_task(
            run_login_page(
                auth,
                store,
                settings.login_host,
                settings.login_port,
                settings.open_browser,
                on_ready=ready.set_result,
            )
        )
        await asyncio.wait({login_task, ready}, return_when=asyncio.FIRST_COMPLETED)
        if not ready.done():
            try:
                login_task.result()
            except Exception as error:
                return f"Could not start the login page: {error}"
            return "Could not start the login page."
        url = ready.result()
        return (
            f"Open {url} in a browser and sign in with your ITMO credentials. "
            "Then call auth_status to confirm."
        )

    @app.tool()
    async def auth_status() -> dict:
        """Report whether a valid my.itmo.ru session exists."""
        try:
            access_token = await client._valid_access_token()
            response = await http.get(
                settings.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except (AuthRequired, httpx.HTTPError):
            return {"authenticated": False}
        tokens = store.load()
        if tokens is None:
            return {"authenticated": False}
        claims = response.json()
        return {
            "authenticated": True,
            "isu": claims.get("isu"),
            "preferred_username": claims.get("preferred_username"),
            "expires_at": tokens.access_expires_at,
        }

    @app.tool()
    async def logout() -> str:
        """Drop the stored my.itmo.ru session."""
        tokens = store.load()
        try:
            if tokens is not None:
                await auth.logout(tokens.refresh_token)
        except httpx.HTTPError:
            pass
        finally:
            store.clear()
        return "Logged out."


def create_app(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.load()
    http = httpx.AsyncClient(timeout=30)
    store = TokenStore(settings.token_path)
    auth = KeycloakAuth(settings, http)
    client = MyItmoClient(settings, store, auth, http)

    app = FastMCP(
        "my-itmo",
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path=settings.mcp_path,
    )
    _register_auth(app, settings, http, store, auth, client)
    for feature in FEATURES:
        feature.register(app, client)
    return app
