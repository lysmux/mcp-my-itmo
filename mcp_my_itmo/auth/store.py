import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TokenSet:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    id_token: str | None = field(repr=False)
    access_expires_at: float
    refresh_expires_at: float

    def access_valid(self, skew: float = 30) -> bool:
        return self.access_expires_at > time.time() + skew

    def refresh_valid(self, skew: float = 30) -> bool:
        return self.refresh_expires_at > time.time() + skew


class TokenStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> TokenSet | None:
        try:
            return TokenSet(**json.loads(self._path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    def save(self, tokens: TokenSet) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            if os.name != "nt":
                os.fchmod(file.fileno(), 0o600)
            file.write(json.dumps(asdict(tokens)))

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)
