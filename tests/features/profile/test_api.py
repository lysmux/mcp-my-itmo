import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.core.client import AuthRequired, MyItmoClient
from mcp_my_itmo.config import Settings
from mcp_my_itmo.features.profile import api
from mcp_my_itmo.features.profile.models import Profile
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures"
USERINFO_URL = Settings().userinfo_endpoint


def userinfo() -> dict:
    return json.loads((FIXTURES / "userinfo.json").read_text(encoding="utf-8"))


async def build_client(tmp_path, tokens, auth_result=None):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(tokens)
    http = httpx.AsyncClient()
    auth = FakeAuth(auth_result or make_tokens("x"))
    return MyItmoClient(Settings(), store, auth, http), http


def test_fixture_parses_into_profile():
    profile = Profile.model_validate(userinfo())

    assert profile.isu == 123456
    assert profile.name == "Ivan Ivanov"
    assert (profile.given_name, profile.family_name, profile.middle_name) == (
        "Ivan",
        "Ivanov",
        "Ivanovich",
    )
    assert profile.email == "user@example.com"
    assert profile.edu_email == "user@niuitmo.example"
    assert profile.groups == ["M3100"]
    assert profile.is_student is True


def test_profile_tolerates_missing_optional_fields():
    raw = userinfo()
    for key in ("middle_name", "edu_email", "groups", "is_student"):
        del raw[key]

    profile = Profile.model_validate(raw)

    assert profile.middle_name is None
    assert profile.edu_email is None
    assert profile.groups == []
    assert profile.is_student is None


def test_profile_treats_null_groups_as_empty():
    profile = Profile.model_validate({**userinfo(), "groups": None})

    assert profile.groups == []


@respx.mock
async def test_get_profile_sends_bearer_to_userinfo_endpoint(tmp_path):
    route = respx.get(USERINFO_URL).respond(json=userinfo())
    client, http = await build_client(tmp_path, make_tokens("access-1"))

    profile = await api.get_profile(client)
    await http.aclose()

    assert profile.isu == 123456
    request = route.calls.last.request
    assert str(request.url) == USERINFO_URL
    assert request.headers["Authorization"] == "Bearer access-1"


@respx.mock
async def test_userinfo_401_without_refresh_raises_auth_required(tmp_path):
    respx.get(USERINFO_URL).respond(401)
    tokens = make_tokens("access-1", refresh_ttl=-10)
    client, http = await build_client(tmp_path, tokens)

    with pytest.raises(AuthRequired):
        await api.get_profile(client)
    await http.aclose()
