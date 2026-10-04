from __future__ import annotations

from pydantic import BaseModel

# Shape per go-itmo (myitmo/qr.go), live-verify pending.


class QrPass(BaseModel):
    qr_hex: str | None = None
