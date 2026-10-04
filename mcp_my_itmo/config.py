from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_REALM_BASE = "https://id.itmo.ru/auth/realms/itmo"
DEFAULT_API_BASE = "https://my.itmo.ru/api"


def default_token_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if os.name == "nt" and appdata:
        return Path(appdata) / "mcp-my-itmo" / "tokens.json"
    return Path.home() / ".config" / "mcp-my-itmo" / "tokens.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MY_ITMO_", env_ignore_empty=True, frozen=True)

    realm_base: str = DEFAULT_REALM_BASE
    client_id: str = "student-personal-cabinet"
    redirect_uri: str = "https://my.itmo.ru/login"
    scope: str = "openid profile"
    code_challenge_method: str = "S256"
    api_base: str = DEFAULT_API_BASE
    token_path: Path = Field(default_factory=default_token_path)
    login_host: str = "127.0.0.1"
    login_port: int = 0
    open_browser: bool = True
    transport: Literal["stdio", "streamable-http"] = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_path: str = "/mcp"

    @property
    def auth_endpoint(self) -> str:
        return f"{self.realm_base}/protocol/openid-connect/auth"

    @property
    def token_endpoint(self) -> str:
        return f"{self.realm_base}/protocol/openid-connect/token"

    @property
    def userinfo_endpoint(self) -> str:
        return f"{self.realm_base}/protocol/openid-connect/userinfo"

    @property
    def logout_endpoint(self) -> str:
        return f"{self.realm_base}/protocol/openid-connect/logout"

    @classmethod
    def load(cls) -> Settings:
        return cls()
