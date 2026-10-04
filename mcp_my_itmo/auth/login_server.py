from __future__ import annotations

import asyncio
import webbrowser
from dataclasses import dataclass
from html import escape
from typing import Callable
from urllib.parse import parse_qs

from ..logging_setup import get_logger
from .keycloak import InvalidCredentials, KeycloakAuth, OTPRequired
from .store import TokenStore

log = get_logger(__name__)

MAX_BODY_BYTES = 16 * 1024
LOGIN_TIMEOUT_SECONDS = 600


class BadRequest(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


@dataclass
class LoginResult:
    ok: bool
    message: str


def _page(body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>my.itmo.ru login</title></head><body>"
        f"{body}</body></html>"
    )


def _form_page(notice: str = "", username: str = "", ask_otp: bool = False) -> str:
    notice_html = f"<p>{escape(notice)}</p>" if notice else ""
    otp_label = "One-time code (required)" if ask_otp else "One-time code (if enabled)"
    return _page(
        "<h1>Sign in to my.itmo.ru</h1>"
        f"{notice_html}"
        "<form method='post' action='/'>"
        f"<p><label>Username <input name='username' value='{escape(username, quote=True)}'></label></p>"
        "<p><label>Password <input name='password' type='password'></label></p>"
        f"<p><label>{otp_label} <input name='otp' autocomplete='one-time-code'></label></p>"
        "<p><button type='submit'>Sign in</button></p>"
        "</form>"
    )


def _http_response(status: str, html: str) -> bytes:
    body = html.encode("utf-8")
    head = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n"
    )
    return head.encode("ascii") + body


async def _read_request(reader: asyncio.StreamReader) -> tuple[str, dict[str, list[str]]]:
    head = await reader.readuntil(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    method = lines[0].split(" ", 1)[0]
    length = 0
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() == "content-length":
            try:
                length = int(value.strip() or 0)
            except ValueError:
                raise BadRequest("400 Bad Request") from None
            if length < 0:
                raise BadRequest("400 Bad Request")
            if length > MAX_BODY_BYTES:
                raise BadRequest("413 Payload Too Large")
    body = await reader.readexactly(length) if length else b""
    return method, parse_qs(body.decode("utf-8"), keep_blank_values=True)


async def run_login_page(
    auth: KeycloakAuth,
    store: TokenStore,
    host: str,
    port: int,
    open_browser: bool,
    on_ready: Callable[[str], None] | None = None,
    timeout: float = LOGIN_TIMEOUT_SECONDS,
) -> LoginResult:
    done: asyncio.Future[LoginResult] = asyncio.get_running_loop().create_future()

    async def authenticate(fields: dict[str, list[str]]) -> str:
        username = fields.get("username", [""])[0]
        password = fields.get("password", [""])[0]
        otp = fields.get("otp", [""])[0].strip()

        async def otp_provider() -> str:
            return otp

        try:
            tokens = await auth.login_with_password(
                username, password, otp_provider if otp else None
            )
        except OTPRequired:
            return _form_page("A one-time code is required.", username, ask_otp=True)
        except InvalidCredentials:
            return _form_page("Invalid username or password.", username)
        except Exception as error:
            return _form_page(f"Login failed: {type(error).__name__}", username)
        try:
            store.save(tokens)
        except OSError as error:
            if not done.done():
                done.set_result(LoginResult(False, f"Could not save tokens: {error}"))
            return _page("<h1>Login failed</h1><p>Could not save the session.</p>")
        if not done.done():
            done.set_result(LoginResult(True, "Logged in to my.itmo.ru."))
        return _page("<h1>Signed in</h1><p>You can close this tab.</p>")

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            method, fields = await _read_request(reader)
            html = await authenticate(fields) if method == "POST" else _form_page()
            writer.write(_http_response("200 OK", html))
            await writer.drain()
        except BadRequest as error:
            writer.write(_http_response(error.status, _page(f"<p>{error.status}</p>")))
            await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port)
    url = f"http://{host}:{server.sockets[0].getsockname()[1]}/"
    log.info("login_page_started", host=host, port=server.sockets[0].getsockname()[1])
    if on_ready is not None:
        on_ready(url)
    if open_browser:
        webbrowser.open(url)
    try:
        return await asyncio.wait_for(done, timeout)
    except asyncio.TimeoutError:
        return LoginResult(False, "Login page timed out without a login.")
    finally:
        server.close()
        await server.wait_closed()
