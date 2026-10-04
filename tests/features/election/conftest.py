import json
from pathlib import Path

import httpx
import pytest

from mcp_my_itmo.auth.store import TokenStore
from mcp_my_itmo.config import Settings
from mcp_my_itmo.core.client import MyItmoClient
from tests.core.test_client import FakeAuth, make_tokens

FIXTURES = Path(__file__).parents[2] / "fixtures" / "election"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
async def client(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(make_tokens("access-1"))
    http = httpx.AsyncClient()
    yield MyItmoClient(Settings(), store, FakeAuth(make_tokens("x")), http)
    await http.aclose()
