from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class Lesson(BaseModel):
    subject: str | None = None
    type: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    teacher_name: str | None = None
    room: str | None = None
    building: str | None = None
    format: str | None = None
    group: str | None = None
    note: str | None = None


class ScheduleDay(BaseModel):
    day: date = Field(alias="date")
    lessons: list[Lesson] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @field_validator("lessons", mode="before")
    @classmethod
    def _null_lessons_as_empty(cls, value):
        return [] if value is None else value


class ScheduleWeek(BaseModel):
    days: list[ScheduleDay] = Field(default_factory=list)

    @classmethod
    def from_envelope(cls, envelope: dict) -> ScheduleWeek:
        raw_days = envelope.get("data") or []
        return cls(days=[ScheduleDay.model_validate(raw) for raw in raw_days])


class TimeSlot(BaseModel):
    order: int
    time_start: str
    time_end: str
