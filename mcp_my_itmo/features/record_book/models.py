from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SemesterInfo(BaseModel):
    study_year: str | None = None
    semester: int
    sem_id: int | None = None
    course: int | None = None
    actual: bool = False


class Specialization(BaseModel):
    main_plan: int
    specialization_name: str | None = None
    semesters: list[SemesterInfo] = Field(default_factory=list)

    @field_validator("semesters", mode="before")
    @classmethod
    def _null_semesters_as_empty(cls, value):
        return [] if value is None else value


class Teacher(BaseModel):
    surname: str | None = None
    name: str | None = None
    patronymic: str | None = None


class SubjectMark(BaseModel):
    name: str | None = None
    discipline_id: int | None = None
    est_id: int | None = None
    current_score: float | None = None
    rate: str | None = None
    attempt: int | None = None
    control_type: str | None = None
    control_type_id: int | None = None
    exam_date: str | None = None
    teacher: Teacher | None = None
