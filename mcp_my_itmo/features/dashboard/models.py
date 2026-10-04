from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

# Shapes per go-itmo (myitmo/system.go), live-verify pending.

ItemList = BeforeValidator(lambda value: [] if value is None else value)


class DashboardWidget(BaseModel):
    i: str | None = None
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None
    widget: str | None = None
    min_w: int | None = None
    max_w: int | None = None
    min_h: int | None = None
    max_h: int | None = None


class MenuItem(BaseModel):
    title: str | None = None
    description: str | None = None
    to: str | None = None
    icon: str | None = None
    children: Annotated[list["MenuItem"], ItemList] = Field(default_factory=list)
