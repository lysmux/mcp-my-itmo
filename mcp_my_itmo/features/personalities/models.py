from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, computed_field

# Shapes per go-itmo (myitmo/personalities.go); live-verify pending.


def _flexible_id(value):
    return None if value is None else str(value)


def _empty_if_none(value):
    return [] if value is None else value


FlexId = Annotated[str | None, BeforeValidator(_flexible_id)]
ItemList = BeforeValidator(_empty_if_none)


class PersonSummary(BaseModel):
    id: int | None = None
    fio: str | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    work: str | None = None
    education: str | None = None
    photo: str | None = None


class Contact(BaseModel):
    contact_alias: str | None = None
    contact: Annotated[list[str], ItemList] = Field(default_factory=list)


class Room(BaseModel):
    room_number: str | None = None
    building_name: str | None = Field(default=None, alias="bld_name")


class Position(BaseModel):
    department_name: str | None = None
    department_link: str | None = None
    position_name: str | None = None
    sorting: FlexId = None
    vacation: dict | list | str | int | None = Field(default=None, exclude=True)
    start_vacation: str | None = None
    end_vacation: str | None = None

    @computed_field
    @property
    def on_vacation(self) -> bool:
        return bool(self.vacation)


class Education(BaseModel):
    course: str | None = None
    faculty_name: str | None = None
    group: str | None = None


class Power(BaseModel):
    power_id: int | None = None
    power_name: str | None = None
    dep_name: str | None = None
    dep_link: str | None = None


class Levels(BaseModel):
    rank: str | None = None
    degree: str | None = None


class Person(BaseModel):
    isu: int | None = None
    fio: str | None = None
    gender: str | None = None
    photo: str | None = None
    contacts: Annotated[list[Contact], ItemList] = Field(default_factory=list)
    rooms: Annotated[list[Room], ItemList] = Field(default_factory=list)
    positions: Annotated[list[Position], ItemList] = Field(default_factory=list)
    education: Annotated[list[Education], ItemList] = Field(default_factory=list)
    powers: Annotated[list[Power], ItemList] = Field(default_factory=list)
    levels: Levels | None = None
    exchange_training: bool = False
