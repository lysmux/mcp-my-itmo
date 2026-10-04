import asyncio
import contextlib

import httpx
import pytest

from mcp_my_itmo.auth.keycloak import InvalidCredentials, OTPRequired
from mcp_my_itmo.auth.login_server import run_login_page
from mcp_my_itmo.auth.store import TokenSet, TokenStore

TOKENS = TokenSet("a", "r", None, 1e12, 1e12)


class FakeAuth:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    async def login_with_password(self, username, password, otp_provider=None):
        self.calls.append((username, password, otp_provider))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


async def start(auth, store):
    ready: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(
        run_login_page(auth, store, "127.0.0.1", 0, False, on_ready=ready.set_result)
    )
    return task, await ready


async def stop(task):
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.fixture
def store(tmp_path):
    return TokenStore(tmp_path / "tokens.json")


async def test_get_serves_form(store):
    task, url = await start(FakeAuth(TOKENS), store)
    async with httpx.AsyncClient() as client:
        html = (await client.get(url)).text
    await stop(task)
    for field in ("name='username'", "name='password'", "name='otp'"):
        assert field in html


async def test_post_success_saves_tokens_and_finishes(store):
    auth = FakeAuth(TOKENS)
    task, url = await start(auth, store)
    async with httpx.AsyncClient() as client:
        await client.post(url, data={"username": "u", "password": "p", "otp": ""})
    result = await asyncio.wait_for(task, 5)
    assert result.ok
    assert store.load() == TOKENS
    assert auth.calls[0][:2] == ("u", "p")
    assert auth.calls[0][2] is None


async def test_post_with_otp_passes_provider(store):
    auth = FakeAuth(TOKENS)
    task, url = await start(auth, store)
    async with httpx.AsyncClient() as client:
        await client.post(url, data={"username": "u", "password": "p", "otp": "123456"})
    await asyncio.wait_for(task, 5)
    assert await auth.calls[0][2]() == "123456"


async def test_invalid_credentials_renders_error_without_tokens(store):
    task, url = await start(FakeAuth(InvalidCredentials()), store)
    async with httpx.AsyncClient() as client:
        html = (await client.post(url, data={"username": "u", "password": "x"})).text
    await stop(task)
    assert "Invalid username or password" in html
    assert store.load() is None


async def test_otp_required_asks_for_code_without_tokens(store):
    task, url = await start(FakeAuth(OTPRequired()), store)
    async with httpx.AsyncClient() as client:
        html = (await client.post(url, data={"username": "u", "password": "p"})).text
    await stop(task)
    assert "one-time code is required" in html
    assert store.load() is None


async def test_unexpected_error_renders_error_without_tokens(store):
    task, url = await start(FakeAuth(RuntimeError("boom")), store)
    async with httpx.AsyncClient() as client:
        html = (await client.post(url, data={"username": "u", "password": "p"})).text
    await stop(task)
    assert "Login failed" in html
    assert "boom" not in html
    assert store.load() is None


async def test_save_failure_resolves_with_error(store, monkeypatch):
    def failing_save(tokens):
        raise OSError("disk full")

    monkeypatch.setattr(store, "save", failing_save)
    task, url = await start(FakeAuth(TOKENS), store)
    async with httpx.AsyncClient() as client:
        html = (await client.post(url, data={"username": "u", "password": "p"})).text
    result = await asyncio.wait_for(task, 5)
    assert not result.ok
    assert "Could not save" in html


async def test_idle_page_times_out(store):
    result = await asyncio.wait_for(
        run_login_page(FakeAuth(TOKENS), store, "127.0.0.1", 0, False, timeout=0.05), 5
    )
    assert not result.ok


async def raw_request(url, payload: bytes) -> bytes:
    host, port = url.removeprefix("http://").rstrip("/").split(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(payload)
    await writer.drain()
    response = await reader.read()
    writer.close()
    return response


async def test_malformed_content_length_gets_400(store):
    task, url = await start(FakeAuth(TOKENS), store)
    response = await raw_request(url, b"POST / HTTP/1.1\r\nContent-Length: abc\r\n\r\n")
    await stop(task)
    assert response.startswith(b"HTTP/1.1 400")


async def test_oversize_content_length_gets_413(store):
    task, url = await start(FakeAuth(TOKENS), store)
    response = await raw_request(url, b"POST / HTTP/1.1\r\nContent-Length: 99999\r\n\r\n")
    await stop(task)
    assert response.startswith(b"HTTP/1.1 413")
