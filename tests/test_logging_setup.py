import json

import httpx
import pytest
import respx
import structlog

from mcp_my_itmo import logging_setup
from mcp_my_itmo.auth.keycloak import KeycloakAuth
from mcp_my_itmo.config import Settings
from tests.auth.test_keycloak import (
    FIXED_STATE,
    LOGIN_ACTION,
    LOGIN_HTML,
    TOKEN_RESPONSE,
)


@pytest.fixture(autouse=True)
def fresh_logging():
    structlog.reset_defaults()
    logging_setup._configured = False
    yield
    structlog.reset_defaults()
    logging_setup._configured = False


def json_lines(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_event_is_single_json_line_with_event_level_and_timestamp(capsys):
    logging_setup.setup_logging()

    logging_setup.get_logger("test").info("something_happened", user="alice")

    lines = json_lines(capsys.readouterr().err)
    assert len(lines) == 1
    assert lines[0]["event"] == "something_happened"
    assert lines[0]["level"] == "info"
    assert lines[0]["user"] == "alice"
    assert "T" in lines[0]["timestamp"]


def test_setup_logging_is_idempotent(capsys):
    logging_setup.setup_logging()
    processors_after_first = list(structlog.get_config()["processors"])
    logging_setup.setup_logging()

    logging_setup.get_logger().info("once")

    assert structlog.get_config()["processors"] == processors_after_first
    assert len(json_lines(capsys.readouterr().err)) == 1


def test_level_filters_lower_severity_events(capsys):
    logging_setup.setup_logging("WARNING")

    logging_setup.get_logger().info("hidden")
    logging_setup.get_logger().warning("shown")

    events = [line["event"] for line in json_lines(capsys.readouterr().err)]
    assert events == ["shown"]


async def test_login_and_refresh_logs_never_contain_secrets(capsys, monkeypatch):
    from mcp_my_itmo.auth import keycloak

    monkeypatch.setattr(keycloak, "make_state", lambda: FIXED_STATE)
    logging_setup.setup_logging()
    password = "SENTINEL-PASSWORD-123"
    settings = Settings()

    async with httpx.AsyncClient() as client:
        auth = KeycloakAuth(settings, client)
        with respx.mock:
            respx.get(settings.auth_endpoint).respond(200, html=LOGIN_HTML)
            respx.post(url__startswith=LOGIN_ACTION.split("?")[0]).respond(
                302,
                headers={
                    "Location": f"https://my.itmo.ru/login?code=SENTINEL-CODE&state={FIXED_STATE}"
                },
            )
            respx.post(settings.token_endpoint).respond(200, json=TOKEN_RESPONSE)
            await auth.login_with_password("alice", password)
            await auth.refresh("SENTINEL-REFRESH")

    output = capsys.readouterr().err
    events = [line["event"] for line in json_lines(output)]
    assert events == ["login_started", "login_succeeded", "token_refreshed"]
    for secret in (
        password,
        "SENTINEL-CODE",
        "SENTINEL-REFRESH",
        TOKEN_RESPONSE["access_token"],
        TOKEN_RESPONSE["refresh_token"],
        TOKEN_RESPONSE["id_token"],
    ):
        assert secret not in output
