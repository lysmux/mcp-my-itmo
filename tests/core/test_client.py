import asyncio
import time

import httpx
import pytest
import respx

from mcp_my_itmo.auth.store import TokenSet, TokenStore
from mcp_my_itmo.core.client import AuthRequired, MyItmoClient
from mcp_my_itmo.config import Settings

API_URL = "https://my.itmo.ru/api/ping"


def make_tokens(access: str = "access-1", access_ttl: float = 300, refresh_ttl: float = 3600) -> TokenSet:
    now = time.time()
    return TokenSet(
        access_token=access,
        refresh_token=f"refresh-for-{access}",
        id_token=None,
        access_expires_at=now + access_ttl,
        refresh_expires_at=now + refresh_ttl,
    )


class FakeAuth:
    def __init__(self, result: TokenSet | Exception) -> None:
        self._result = result
        self.calls: list[str] = []

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.calls.append(refresh_token)
        await asyncio.sleep(0)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.fixture
def store(tmp_path) -> TokenStore:
    return TokenStore(tmp_path / "tokens.json")


@pytest.fixture
async def http():
    async with httpx.AsyncClient() as client:
        yield client


def build_client(store, http, auth=None) -> MyItmoClient:
    return MyItmoClient(Settings(), store, auth or FakeAuth(make_tokens("unused")), http)


async def test_returns_stored_token_when_access_valid(store, http):
    store.save(make_tokens("access-1"))
    auth = FakeAuth(make_tokens("new"))

    token = await build_client(store, http, auth)._valid_access_token()

    assert token == "access-1"
    assert auth.calls == []


async def test_refreshes_and_persists_when_access_expired(store, http):
    expired = make_tokens("old", access_ttl=-10)
    fresh = make_tokens("fresh")
    store.save(expired)
    auth = FakeAuth(fresh)

    token = await build_client(store, http, auth)._valid_access_token()

    assert token == "fresh"
    assert auth.calls == [expired.refresh_token]
    assert store.load() == fresh


async def test_concurrent_calls_refresh_only_once(store, http):
    store.save(make_tokens("old", access_ttl=-10))
    auth = FakeAuth(make_tokens("fresh"))
    client = build_client(store, http, auth)

    tokens = await asyncio.gather(*(client._valid_access_token() for _ in range(5)))

    assert tokens == ["fresh"] * 5
    assert len(auth.calls) == 1


@respx.mock
async def test_concurrent_401s_refresh_only_once(store, http):
    store.save(make_tokens("stale"))
    auth = FakeAuth(make_tokens("fresh"))

    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers["Authorization"] == "Bearer stale":
            return httpx.Response(401)
        return httpx.Response(200, json={"ok": 1})

    respx.get(API_URL).mock(side_effect=respond)
    client = build_client(store, http, auth)

    bodies = await asyncio.gather(*(client.get("/ping") for _ in range(5)))

    assert bodies == [{"ok": 1}] * 5
    assert len(auth.calls) == 1


async def test_no_tokens_raises_auth_required(store, http):
    with pytest.raises(AuthRequired):
        await build_client(store, http)._valid_access_token()


async def test_refresh_invalid_raises_auth_required(store, http):
    store.save(make_tokens("old", access_ttl=-10, refresh_ttl=-10))
    auth = FakeAuth(make_tokens("fresh"))

    with pytest.raises(AuthRequired):
        await build_client(store, http, auth)._valid_access_token()
    assert auth.calls == []


def status_error(status: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        "bad", request=httpx.Request("POST", "https://x"), response=httpx.Response(status)
    )


@pytest.mark.parametrize("status", [400, 401])
async def test_refresh_rejection_raises_auth_required(store, http, status):
    store.save(make_tokens("old", access_ttl=-10))

    with pytest.raises(AuthRequired):
        await build_client(store, http, FakeAuth(status_error(status)))._valid_access_token()


async def test_transient_refresh_failure_propagates(store, http):
    store.save(make_tokens("old", access_ttl=-10))

    with pytest.raises(httpx.HTTPStatusError):
        await build_client(store, http, FakeAuth(status_error(503)))._valid_access_token()

    with pytest.raises(httpx.ConnectError):
        await build_client(store, http, FakeAuth(httpx.ConnectError("down")))._valid_access_token()


@respx.mock
async def test_get_returns_json_and_sends_bearer(store, http):
    store.save(make_tokens("access-1"))
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

    body = await build_client(store, http).get("/ping", params={"a": "1"})

    assert body == {"ok": True}
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer access-1"
    assert request.url.params["a"] == "1"


@respx.mock
async def test_get_refreshes_once_on_401_and_retries(store, http):
    store.save(make_tokens("stale"))
    fresh = make_tokens("fresh")
    auth = FakeAuth(fresh)
    route = respx.get(API_URL).mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"ok": 1})]
    )

    body = await build_client(store, http, auth).get("/ping")

    assert body == {"ok": 1}
    assert len(auth.calls) == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer stale"
    assert route.calls[1].request.headers["Authorization"] == "Bearer fresh"
    assert store.load() == fresh


@respx.mock
async def test_request_merges_headers_and_resends_them_on_retry(store, http):
    store.save(make_tokens("stale"))
    auth = FakeAuth(make_tokens("fresh"))
    route = respx.post(API_URL).mock(side_effect=[httpx.Response(401), httpx.Response(200)])

    await build_client(store, http, auth).request(
        "POST",
        API_URL,
        content='{"a": 1}',
        headers={"X-Extra": "1", "Authorization": "Bearer hijack"},
    )

    first, second = (call.request for call in route.calls)
    assert first.headers["X-Extra"] == second.headers["X-Extra"] == "1"
    assert first.headers["Authorization"] == "Bearer stale"
    assert second.headers["Authorization"] == "Bearer fresh"
    assert second.content == b'{"a": 1}'


@respx.mock
async def test_get_two_consecutive_401_raises_auth_required(store, http):
    store.save(make_tokens("stale"))
    auth = FakeAuth(make_tokens("fresh"))
    route = respx.get(API_URL).mock(return_value=httpx.Response(401))

    with pytest.raises(AuthRequired):
        await build_client(store, http, auth).get("/ping")
    assert route.call_count == 2
    assert len(auth.calls) == 1


@respx.mock
async def test_get_401_with_invalid_refresh_raises_auth_required(store, http):
    store.save(make_tokens("stale", refresh_ttl=-10))
    route = respx.get(API_URL).mock(return_value=httpx.Response(401))

    with pytest.raises(AuthRequired):
        await build_client(store, http).get("/ping")
    assert route.call_count == 1


@respx.mock
async def test_get_raises_for_other_errors(store, http):
    store.save(make_tokens("access-1"))
    respx.get(API_URL).mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await build_client(store, http).get("/ping")
