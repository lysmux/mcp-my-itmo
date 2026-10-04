from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _null_as_empty_list(value):
    return [] if value is None else value


class SportSemester(BaseModel):
    id: int
    study_year: str | None = None
    semester: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    hard_date_end: str | None = None
    choice_start: str | None = None


class SportScoreSum(BaseModel):
    attendances: int | None = None
    other: int | None = None


class SportAttendance(BaseModel):
    type: str | None = None
    name: str | None = None
    evaluation_name: str | None = None
    score: int | None = None
    date: str | None = None
    is_competition: bool | None = None
    competition_name: str | None = None
    discipline_name: str | None = None
    place: str | None = None


class SportScore(BaseModel):
    sum: SportScoreSum = Field(default_factory=SportScoreSum)
    attendances: list[SportAttendance] = Field(default_factory=list)

    _attendances_default = field_validator("attendances", mode="before")(_null_as_empty_list)

    @field_validator("sum", mode="before")
    @classmethod
    def _sum_default(cls, value):
        return {} if value is None else value


class SportAttempts(BaseModel):
    total_attempts: int | None = None
    used_attempts: int | None = None
    free_attempts: int | None = None
    can_sign_in: bool | None = None


class SportDebt(BaseModel):
    is_having_debt: bool | None = None
    needed_score: float | None = None
    free_attempts: int | None = None


class SportCanSignIn(BaseModel):
    can_sign_in: bool | None = None
    unavailable_reasons: list[str] = Field(default_factory=list)

    _reasons_default = field_validator("unavailable_reasons", mode="before")(
        _null_as_empty_list
    )


class SportLesson(BaseModel):
    id: int
    date: str | None = None
    date_end: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    lesson_group_id: int | None = None
    lesson_level: int | None = None
    type_id: int | None = None
    room_name: str | None = None
    limit: int | None = None
    available: int | None = None
    comment: str | None = None
    time_slot_start: str | None = None
    time_slot_end: str | None = None
    intersection: bool | None = None
    can_sign_in: SportCanSignIn | None = None
    signed: bool | None = None
    teacher_fio: str | None = None
    link_url: str | None = None


class SportScheduleDay(BaseModel):
    date: str | None = None
    lessons: list[SportLesson] = Field(default_factory=list)

    _lessons_default = field_validator("lessons", mode="before")(_null_as_empty_list)


class SportSummary(BaseModel):
    semester: SportSemester | None = None
    score: SportScore | None = None
    attempts: SportAttempts | None = None
    debt: SportDebt | None = None
