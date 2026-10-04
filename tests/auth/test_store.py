import json
import os
import time
from pathlib import Path

import pytest

from mcp_my_itmo.auth.store import TokenSet, TokenStore

NOW = 1_000_000.0


@pytest.fixture
def tokens() -> TokenSet:
    return TokenSet(
        access_token="access",
        refresh_token="refresh",
        id_token=None,
        access_expires_at=NOW + 100,
        refresh_expires_at=NOW + 1000,
    )


def test_save_then_load_round_trips_all_fields(tmp_path: Path, tokens: TokenSet):
    store = TokenStore(tmp_path / "nested" / "tokens.json")
    store.save(tokens)
    assert store.load() == tokens


def test_round_trips_id_token_value(tmp_path: Path, tokens: TokenSet):
    tokens.id_token = "id"
    store = TokenStore(tmp_path / "tokens.json")
    store.save(tokens)
    assert store.load() == tokens


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes only")
def test_saved_file_mode_is_0600(tmp_path: Path, tokens: TokenSet):
    path = tmp_path / "tokens.json"
    TokenStore(path).save(tokens)
    assert path.stat().st_mode & 0o777 == 0o600


def test_load_missing_file_returns_none(tmp_path: Path):
    assert TokenStore(tmp_path / "absent.json").load() is None


def test_load_corrupt_json_returns_none(tmp_path: Path):
    path = tmp_path / "tokens.json"
    path.write_text("{not json")
    assert TokenStore(path).load() is None


def test_load_wrong_shape_returns_none(tmp_path: Path):
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps({"access_token": "a"}))
    assert TokenStore(path).load() is None


def test_clear_removes_file_and_tolerates_absence(tmp_path: Path, tokens: TokenSet):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(tokens)
    store.clear()
    assert store.load() is None
    store.clear()


def test_validity_respects_skew(monkeypatch: pytest.MonkeyPatch, tokens: TokenSet):
    monkeypatch.setattr(time, "time", lambda: NOW)
    assert tokens.access_valid()
    assert tokens.access_valid(skew=99)
    assert not tokens.access_valid(skew=100)
    assert tokens.refresh_valid(skew=999)
    assert not tokens.refresh_valid(skew=1000)
    assert not tokens.refresh_valid(skew=2000)


def test_repr_does_not_leak_secrets(tokens: TokenSet):
    tokens.id_token = "id-secret"
    text = repr(tokens)
    for secret in ("access", "refresh", "id-secret"):
        assert f"'{secret}'" not in text
