from __future__ import annotations

import asyncio

import httpx

from mcp_my_itmo.auth.keycloak import KeycloakAuth
from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings

_REFRESH_REJECTED_STATUSES = frozenset({400, 401})


class AuthRequired(Exception):
    """Raised when there is no usable session and the user must log in again."""


class MyItmoClient:
    def __init__(
        self,
        settings: Settings,
        store: TokenStore,
        auth: KeycloakAuth,
        http: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._store = store
        self._auth = auth
        self._http = http
        self._refresh_lock = asyncio.Lock()

    async def _valid_access_token(self) -> str:
        tokens = self._store.load()
        if tokens is None:
            raise AuthRequired("not logged in")
        if tokens.access_valid():
            return tokens.access_token
        return await self._refreshed_access_token(rejected=None)

    async def _refreshed_access_token(self, rejected: str | None) -> str:
        """Refresh under a lock so concurrent callers share a single refresh.

        ``rejected`` is the access token the API refused (None when it merely
        expired). If the stored token already differs or is valid, another task
        refreshed first and its result is reused.
        """
        async with self._refresh_lock:
            tokens = self._store.load()
            if tokens is None:
                raise AuthRequired("not logged in")
            if rejected is None and tokens.access_valid():
                return tokens.access_token
            if rejected is not None and tokens.access_token != rejected:
                return tokens.access_token
            if not tokens.refresh_valid():
                raise AuthRequired("session expired")
            try:
                refreshed = await self._auth.refresh(tokens.refresh_token)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in _REFRESH_REJECTED_STATUSES:
                    raise AuthRequired("token refresh rejected") from error
                raise
            self._store.save(refreshed)
            return refreshed.access_token

    def api_url(self, path: str) -> str:
        return f"{self._settings.api_base}{path}"

    async def get(self, path: str, params: dict | None = None) -> dict:
        return await self.get_url(self.api_url(path), params)

    @property
    def userinfo_endpoint(self) -> str:
        return self._settings.userinfo_endpoint

    async def get_url(self, url: str, params: dict | None = None) -> dict:
        response = await self.request("GET", url, params=params)
        response.raise_for_status()
        return response.json()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | list | None = None,
        content: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send with the bearer; on 401 refresh once and retry once, else AuthRequired.

        ``headers`` are merged with the bearer, which always wins over a caller Authorization.
        ``content`` is a raw body, sent as is (set its Content-Type via ``headers``).

        Returns the response without status checking so callers can read error bodies.
        """
        sent_token = await self._valid_access_token()
        response = await self._http.request(
            method, url, params=params,
            json=json,
            content=content,
            headers=_with_bearer(headers, sent_token),
        )
        if response.status_code == 401:
            token = await self._refreshed_access_token(rejected=sent_token)
            response = await self._http.request(
                method,
                url,
                params=params,
                json=json,
                content=content,
                headers=_with_bearer(headers, token),
            )
            if response.status_code == 401:
                raise AuthRequired("API rejected refreshed token")
        return response


def _with_bearer(headers: dict[str, str] | None, token: str) -> dict[str, str]:
    return {**(headers or {}), "Authorization": f"Bearer {token}"}
