from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Shapes per go-itmo (myitmo/practices.go); live-verify pending.


def _text(value):
    """The server may send a number or a string where the value is only displayed."""
    return None if value is None else str(value)


def _empty_if_none(value):
    return [] if value is None else value


Text = Annotated[str | None, BeforeValidator(_text)]
ItemList = BeforeValidator(_empty_if_none)


class _Wire(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PracticeCard(_Wire):
    id: int | None = None
    name: str | None = None
    is_current: bool = Field(default=False, alias="isCurrent")
    mark: str | None = None
    badge_color: str | None = Field(default=None, alias="baigColor")
    head_name: str | None = Field(default=None, alias="headName")
    date_from: str | None = Field(default=None, alias="dateFrom")
    date_to: str | None = Field(default=None, alias="dateTo")


class PracticeYear(_Wire):
    year: Text = None
    practices: Annotated[list[PracticeCard], ItemList] = Field(default_factory=list)


class PracticeStage(_Wire):
    stage_number: int | None = Field(default=None, alias="stageNumber")
    stage_name: str | None = Field(default=None, alias="stageName")
    stage_task: str | None = Field(default=None, alias="stageTask")
    date_from: str | None = Field(default=None, alias="dateFrom")
    date_to: str | None = Field(default=None, alias="dateTo")
    duration: int | None = None


class PracticeTask(_Wire):
    topic: str | None = None
    status: str | None = None
    comment: str | None = None
    stages: Annotated[list[PracticeStage], ItemList] = Field(default_factory=list)


class PracticeDetails(_Wire):
    id: int | None = None
    name: str | None = None
    status_order: int | None = None
    date_from: str | None = Field(default=None, alias="dateFrom")
    date_to: str | None = Field(default=None, alias="dateTo")
    place_name: str | None = Field(default=None, alias="placeName")
    department_name: str | None = Field(default=None, alias="departmentName")
    position: str | None = None
    format: str | None = None
    curator_name: str | None = Field(default=None, alias="curatorName")
    curator_email: str | None = Field(default=None, alias="curatorEmail")
    curator_photo: str | None = Field(default=None, alias="curatorPhoto")
    head_itmo_name: str | None = Field(default=None, alias="headItmoName")
    head_itmo_isu: int | None = Field(default=None, alias="HeadItmoIsu")
    head_itmo_email: str | None = Field(default=None, alias="headItmoEmail")
    head_external_name: str | None = Field(default=None, alias="headExternalName")
    head_external_email: str | None = Field(default=None, alias="headExternalEmail")
    task: PracticeTask | None = None
