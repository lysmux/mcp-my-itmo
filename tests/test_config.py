from pathlib import Path

import pytest

from mcp_my_itmo.config import DEFAULT_API_BASE, DEFAULT_REALM_BASE, Settings

ENV_NAMES = (
    "REALM_BASE",
    "CLIENT_ID",
    "REDIRECT_URI",
    "SCOPE",
    "API_BASE",
    "TOKEN_PATH",
    "LOGIN_HOST",
    "LOGIN_PORT",
    "OPEN_BROWSER",
    "MCP_HOST",
    "MCP_PORT",
    "MCP_PATH",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(f"MY_ITMO_{name}", raising=False)


def test_defaults_match_previous_values():
    settings = Settings()
    assert settings.realm_base == DEFAULT_REALM_BASE
    assert settings.client_id == "student-personal-cabinet"
    assert settings.redirect_uri == "https://my.itmo.ru/login"
    assert settings.scope == "openid profile"
    assert settings.code_challenge_method == "S256"
    assert settings.api_base == DEFAULT_API_BASE
    assert settings.token_path.name == "tokens.json"
    assert (settings.login_host, settings.login_port, settings.open_browser) == (
        "127.0.0.1",
        0,
        True,
    )
    assert (settings.mcp_host, settings.mcp_port, settings.mcp_path) == ("127.0.0.1", 8000, "/mcp")


def test_env_overrides_are_read_by_plain_constructor(monkeypatch, tmp_path):
    token_path = tmp_path / "t.json"
    monkeypatch.setenv("MY_ITMO_TOKEN_PATH", str(token_path))
    monkeypatch.setenv("MY_ITMO_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MY_ITMO_MCP_PORT", "9001")
    monkeypatch.setenv("MY_ITMO_MCP_PATH", "/x")
    monkeypatch.setenv("MY_ITMO_LOGIN_HOST", "localhost")
    monkeypatch.setenv("MY_ITMO_LOGIN_PORT", "5555")
    monkeypatch.setenv("MY_ITMO_OPEN_BROWSER", "false")
    settings = Settings()
    assert settings.token_path == Path(token_path)
    assert (settings.mcp_host, settings.mcp_port, settings.mcp_path) == ("0.0.0.0", 9001, "/x")
    assert (settings.login_host, settings.login_port, settings.open_browser) == (
        "localhost",
        5555,
        False,
    )


def test_load_reflects_env(monkeypatch):
    monkeypatch.setenv("MY_ITMO_MCP_PORT", "9002")
    monkeypatch.setenv("MY_ITMO_CLIENT_ID", "other")
    settings = Settings.load()
    assert settings.mcp_port == 9002
    assert settings.client_id == "other"


def test_endpoints_derive_from_realm_base(monkeypatch):
    monkeypatch.setenv("MY_ITMO_REALM_BASE", "https://idp.example/realms/r")
    settings = Settings()
    base = "https://idp.example/realms/r/protocol/openid-connect"
    assert settings.auth_endpoint == f"{base}/auth"
    assert settings.token_endpoint == f"{base}/token"
    assert settings.userinfo_endpoint == f"{base}/userinfo"
    assert settings.logout_endpoint == f"{base}/logout"


def test_empty_env_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MY_ITMO_TOKEN_PATH", "")
    monkeypatch.setenv("MY_ITMO_MCP_HOST", "")
    settings = Settings()
    assert settings.token_path == Settings.model_fields["token_path"].default_factory()
    assert settings.token_path != Path("")
    assert settings.mcp_host == "127.0.0.1"
