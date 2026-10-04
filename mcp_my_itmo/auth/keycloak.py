from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Awaitable, Callable
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from ..config import Settings
from ..logging_setup import get_logger
from .pkce import make_challenge, make_state, make_verifier
from .store import TokenSet


log = get_logger(__name__)


class InvalidCredentials(Exception):
    pass


class OTPRequired(Exception):
    pass


@dataclass
class LoginForm:
    action: str
    fields: dict[str, str]


class _LoginFormParser(HTMLParser):
    """Collects the first <form>'s action plus its hidden/prefilled inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._in_form = False
        self._otp_input = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: (value or "") for key, value in attrs}
        if tag == "form":
            self._in_form = True
            if self.action is None:
                self.action = values.get("action")
            return
        if tag == "input":
            name = values.get("name", "")
            if _is_otp_field(name, values.get("id", ""), values.get("type", "")):
                self._otp_input = True
            if not self._in_form:
                return
            input_type = values.get("type", "").lower()
            if input_type in {"submit", "button", "password"}:
                return
            if name and (input_type == "hidden" or values.get("value")):
                self.fields[name] = values.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._in_form = False


def _is_otp_field(name: str, element_id: str, input_type: str) -> bool:
    haystack = f"{name} {element_id}".lower()
    if "otp" in haystack or "totp" in haystack:
        return True
    return input_type.lower() == "one-time-code"


_LOGIN_ACTION_RE = re.compile(r'"loginAction"\s*:\s*"([^"]+)"')
_PAGE_ID_RE = re.compile(r'"pageId"\s*:\s*"([^"]+)"')


def _kc_login_action(html: str) -> str | None:
    match = _LOGIN_ACTION_RE.search(html)
    if not match:
        return None
    return match.group(1).replace("\\/", "/")


class KeycloakAuth:
    """Drives Keycloak authorization-code + PKCE against the HTML login form.

    The public ``student-personal-cabinet`` client has all direct grants
    disabled, so tokens are obtainable only by submitting the Keycloak login
    form server-side and exchanging the returned authorization code.
    """

    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    def authorize_url(self, challenge: str, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._settings.client_id,
                "redirect_uri": self._settings.redirect_uri,
                "response_type": "code",
                "scope": self._settings.scope,
                "code_challenge_method": self._settings.code_challenge_method,
                "code_challenge": challenge,
                "state": state,
            }
        )
        return f"{self._settings.auth_endpoint}?{query}"

    def parse_login_form(self, html: str) -> LoginForm:
        parser = _LoginFormParser()
        parser.feed(html)
        if parser.action:
            return LoginForm(action=parser.action, fields=parser.fields)
        action = _kc_login_action(html)
        if action is None:
            raise ValueError("no login form action found in page")
        return LoginForm(action=action, fields={})

    def is_otp_form(self, html: str) -> bool:
        page_id = _PAGE_ID_RE.search(html)
        if page_id and "otp" in page_id.group(1).lower():
            return True
        parser = _LoginFormParser()
        parser.feed(html)
        return parser._otp_input

    async def login_with_password(
        self,
        username: str,
        password: str,
        otp_provider: Callable[[], Awaitable[str]] | None = None,
    ) -> TokenSet:
        log.info("login_started", username=username)
        verifier = make_verifier()
        challenge = make_challenge(verifier)
        state = make_state()

        page = await self._http.get(
            self.authorize_url(challenge, state), follow_redirects=True
        )
        form = self.parse_login_form(page.text)

        response = await self._http.post(
            form.action,
            data={**form.fields, "username": username, "password": password},
            follow_redirects=False,
        )

        if response.status_code not in (301, 302, 303, 307, 308):
            if self.is_otp_form(response.text):
                if otp_provider is None:
                    raise OTPRequired("second factor (OTP) required")
                otp_form = self.parse_login_form(response.text)
                code = await otp_provider()
                response = await self._http.post(
                    otp_form.action,
                    data={**otp_form.fields, "otp": code},
                    follow_redirects=False,
                )
            else:
                raise InvalidCredentials("login rejected by Keycloak")

        if response.status_code not in (301, 302, 303, 307, 308):
            raise InvalidCredentials("login did not complete")

        auth_code = self._extract_code(response.headers.get("location", ""), state)
        tokens = await self._exchange_code(auth_code, verifier)
        log.info("login_succeeded", username=username)
        return tokens

    async def _exchange_code(self, code: str, verifier: str) -> TokenSet:
        response = await self._http.post(
            self._settings.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.redirect_uri,
                "client_id": self._settings.client_id,
                "code_verifier": verifier,
            },
        )
        response.raise_for_status()
        return self._token_set(response.json())

    async def refresh(self, refresh_token: str) -> TokenSet:
        response = await self._http.post(
            self._settings.token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._settings.client_id,
            },
        )
        response.raise_for_status()
        tokens = self._token_set(response.json())
        log.info("token_refreshed")
        return tokens

    async def logout(self, refresh_token: str) -> None:
        try:
            await self._http.post(
                self._settings.logout_endpoint,
                data={
                    "client_id": self._settings.client_id,
                    "refresh_token": refresh_token,
                },
            )
        except httpx.HTTPError:
            pass

    def _extract_code(self, location: str, expected_state: str) -> str:
        query = parse_qs(urlparse(location).query)
        returned_state = query.get("state", [None])[0]
        if returned_state != expected_state:
            raise ValueError("state mismatch on authorization redirect")
        codes = query.get("code")
        if not codes:
            raise ValueError("authorization redirect carried no code")
        return codes[0]

    def _token_set(self, payload: dict) -> TokenSet:
        now = time.time()
        return TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            id_token=payload.get("id_token"),
            access_expires_at=now + payload["expires_in"],
            refresh_expires_at=now + payload["refresh_expires_in"],
        )
