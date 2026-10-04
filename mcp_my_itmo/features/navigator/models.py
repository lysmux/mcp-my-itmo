from __future__ import annotations

from pydantic import BaseModel

# Shape per go-itmo (myitmo/navigator.go), live-verify pending.


class NavigatorBuilding(BaseModel):
    building_id: int | None = None
    name: str | None = None
    bounds: list[float] | None = None
    bearing: float | None = None
