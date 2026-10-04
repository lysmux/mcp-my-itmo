import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from mcp_my_itmo.auth import keycloak
from mcp_my_itmo.auth.keycloak import (
    InvalidCredentials,
    KeycloakAuth,
    LoginForm,
    OTPRequired,
)
from mcp_my_itmo.auth.store import TokenSet
from mcp_my_itmo.config import Settings

FIXTURES = Path(__file__).parent.parent / "fixtures"
LOGIN_HTML = (FIXTURES / "login_page.html").read_text(encoding="utf-8")
OTP_HTML = (FIXTURES / "otp_page.html").read_text(encoding="utf-8")

LOGIN_ACTION = (
    "https://id.itmo.ru/auth/realms/itmo/login-actions/authenticate"
    "?session_code=YJ0hJytMbDbFvouJ6a_WkH-6e0aZbm6cgXKo6sfZjgI"
    "&execution=7db2448a-e998-4527-8831-184f67f677f9"
    "&client_id=student-personal-cabinet"
    "&tab_id=SOYqCda8Hxg"
    "&client_data=eyJydSI6Imh0dHBzOi8vbXkuaXRtby5ydS9sb2dpbiIsInJ0IjoiY29kZSIsInN0IjoicHJvYmUifQ"
)

FIXED_STATE = "fixed-state-value"
FIXED_VERIFIER = "fixed-code-verifier-0123456789abcdef0123456789abcdef"

TOKEN_RESPONSE = {
    "access_token": "the-access-token",
    "refresh_token": "the-refresh-token",
    "id_token": "the-id-token",
    "expires_in": 300,
    "refresh_expires_in": 1800,
    "token_type": "Bearer",
}


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def pinned_pkce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(keycloak, "make_state", lambda: FIXED_STATE)
    monkeypatch.setattr(keycloak, "make_verifier", lambda: FIXED_VERIFIER)


def test_authorize_url_contains_all_required_parameters(settings: Settings):
    auth = KeycloakAuth(settings, httpx.AsyncClient())
    url = auth.authorize_url(challenge="the-challenge", state="the-state")

    assert url.startswith(settings.auth_endpoint)
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == [settings.client_id]
    assert query["redirect_uri"] == [settings.redirect_uri]
    assert query["response_type"] == ["code"]
    assert query["scope"] == [settings.scope]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == ["the-challenge"]
    assert query["state"] == ["the-state"]


def test_parse_login_form_returns_keycloakify_action(settings: Settings):
    auth = KeycloakAuth(settings, httpx.AsyncClient())
    form = auth.parse_login_form(LOGIN_HTML)

    assert isinstance(form, LoginForm)
    assert form.action == LOGIN_ACTION
    assert form.fields == {}


def test_parse_login_form_collects_classic_hidden_inputs(settings: Settings):
    html = """
    <form id="kc-form-login" action="https://kc/login-actions/authenticate?x=1" method="post">
      <input type="hidden" name="session_code" value="SC" />
      <input type="hidden" name="execution" value="EX" />
      <input type="text" name="username" />
      <input type="password" name="password" />
      <input type="submit" name="login" value="Sign In" />
    </form>
    """
    auth = KeycloakAuth(settings, httpx.AsyncClient())
    form = auth.parse_login_form(html)

    assert form.action == "https://kc/login-actions/authenticate?x=1"
    assert form.fields == {"session_code": "SC", "execution": "EX"}


def test_is_otp_form_true_on_otp_page_false_on_login_page(settings: Settings):
    auth = KeycloakAuth(settings, httpx.AsyncClient())
    assert auth.is_otp_form(OTP_HTML) is True
    assert auth.is_otp_form(LOGIN_HTML) is False


async def test_login_with_password_happy_path(
    settings: Settings, pinned_pkce: None
):
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock(assert_all_called=True) as mock:
            mock.get(settings.auth_endpoint).respond(
                200, html=LOGIN_HTML
            )
            form_route = mock.post(url__startswith=LOGIN_ACTION.split("?")[0]).respond(
                302,
                headers={
                    "Location": f"https://my.itmo.ru/login?code=AUTHCODE&state={FIXED_STATE}"
                },
            )
            token_route = mock.post(settings.token_endpoint).respond(
                200, json=TOKEN_RESPONSE
            )

            before = time.time()
            tokens = await auth.login_with_password("user", "secret")
            after = time.time()

    assert isinstance(tokens, TokenSet)
    assert tokens.access_token == "the-access-token"
    assert tokens.refresh_token == "the-refresh-token"
    assert tokens.id_token == "the-id-token"
    assert before + 300 <= tokens.access_expires_at <= after + 300
    assert before + 1800 <= tokens.refresh_expires_at <= after + 1800

    form_body = parse_qs(form_route.calls.last.request.content.decode())
    assert form_body["username"] == ["user"]
    assert form_body["password"] == ["secret"]

    token_body = parse_qs(token_route.calls.last.request.content.decode())
    assert token_body["grant_type"] == ["authorization_code"]
    assert token_body["code"] == ["AUTHCODE"]
    assert token_body["code_verifier"] == [FIXED_VERIFIER]
    assert token_body["redirect_uri"] == [settings.redirect_uri]
    assert token_body["client_id"] == [settings.client_id]


async def test_login_with_wrong_credentials_raises_invalid(
    settings: Settings, pinned_pkce: None
):
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock:
            respx.get(settings.auth_endpoint).respond(200, html=LOGIN_HTML)
            respx.post(url__startswith=LOGIN_ACTION.split("?")[0]).respond(
                200, html=LOGIN_HTML
            )
            with pytest.raises(InvalidCredentials):
                await auth.login_with_password("user", "wrong")


async def test_login_requires_otp_without_provider_raises(
    settings: Settings, pinned_pkce: None
):
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock:
            respx.get(settings.auth_endpoint).respond(200, html=LOGIN_HTML)
            respx.post(url__startswith=LOGIN_ACTION.split("?")[0]).respond(
                200, html=OTP_HTML
            )
            with pytest.raises(OTPRequired):
                await auth.login_with_password("user", "secret", otp_provider=None)


async def test_login_with_otp_provider_succeeds(
    settings: Settings, pinned_pkce: None
):
    otp_action_prefix = "https://id.itmo.ru/auth/realms/itmo/login-actions/authenticate"
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock(assert_all_called=True) as mock:
            mock.get(settings.auth_endpoint).respond(200, html=LOGIN_HTML)
            authenticate = mock.post(url__startswith=otp_action_prefix)
            authenticate.side_effect = [
                httpx.Response(200, html=OTP_HTML),
                httpx.Response(
                    302,
                    headers={
                        "Location": f"https://my.itmo.ru/login?code=OTPCODE&state={FIXED_STATE}"
                    },
                ),
            ]
            mock.post(settings.token_endpoint).respond(200, json=TOKEN_RESPONSE)

            async def provide_otp() -> str:
                return "123456"

            tokens = await auth.login_with_password(
                "user", "secret", otp_provider=provide_otp
            )

    assert isinstance(tokens, TokenSet)
    assert tokens.access_token == "the-access-token"
    otp_body = parse_qs(authenticate.calls.last.request.content.decode())
    assert otp_body["otp"] == ["123456"]


async def test_login_rejects_state_mismatch(settings: Settings, pinned_pkce: None):
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock:
            respx.get(settings.auth_endpoint).respond(200, html=LOGIN_HTML)
            respx.post(url__startswith=LOGIN_ACTION.split("?")[0]).respond(
                302,
                headers={
                    "Location": "https://my.itmo.ru/login?code=AUTHCODE&state=tampered"
                },
            )
            with pytest.raises(ValueError):
                await auth.login_with_password("user", "secret")


async def test_refresh_posts_refresh_token_grant(settings: Settings):
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock(assert_all_called=True) as mock:
            token_route = mock.post(settings.token_endpoint).respond(
                200, json=TOKEN_RESPONSE
            )
            before = time.time()
            tokens = await auth.refresh("old-refresh-token")
            after = time.time()

    assert isinstance(tokens, TokenSet)
    assert tokens.access_token == "the-access-token"
    assert before + 300 <= tokens.access_expires_at <= after + 300
    body = parse_qs(token_route.calls.last.request.content.decode())
    assert body["grant_type"] == ["refresh_token"]
    assert body["refresh_token"] == ["old-refresh-token"]
    assert body["client_id"] == [settings.client_id]


async def test_logout_best_effort_swallows_errors(settings: Settings):
    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock(assert_all_called=True) as mock:
            logout_route = mock.post(settings.logout_endpoint).respond(500)
            await auth.logout("some-refresh-token")

    body = parse_qs(logout_route.calls.last.request.content.decode())
    assert body["refresh_token"] == ["some-refresh-token"]
    assert body["client_id"] == [settings.client_id]
