from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _null_as(default_factory):
    def validator(value):
        return default_factory() if value is None else value

    return validator


class StudyProgram(_Model):
    plan_id: int
    specialization_id: int | None = None
    name: str | None = None
    is_active: bool = False


class StudyPrograms(_Model):
    programs: list[StudyProgram] = Field(default_factory=list)

    _programs_not_null = field_validator("programs", mode="before")(_null_as(list))


class PlanInfo(_Model):
    direction_code: str | None = None
    direction_name: str | None = None
    level_qualification: str | None = None
    plan_type: str | None = None
    program_name: str | None = None
    start_year: int | None = None


class Activity(_Model):
    name: str | None = None
    volume: float | None = None
    work_type_id: int | None = None


class Content(_Model):
    semester: int | None = None
    credit_points: int | None = None
    activities: list[Activity] = Field(default_factory=list)

    _activities_not_null = field_validator("activities", mode="before")(_null_as(list))


class PlanNode(_Model):
    name: str | None = None
    type: str | None = None
    credit_points: int | None = None
    children: list[PlanNode] = Field(default_factory=list)
    contents: dict[str, list[Content]] = Field(default_factory=dict)

    _children_not_null = field_validator("children", mode="before")(_null_as(list))
    _contents_not_null = field_validator("contents", mode="before")(_null_as(dict))


class StudyPlan(_Model):
    id: int | None = None
    current_semester: int | None = None
    semesters_count: int | None = None
    plan_info: PlanInfo = Field(default_factory=PlanInfo)
    structure: list[PlanNode] = Field(default_factory=list)

    _structure_not_null = field_validator("structure", mode="before")(_null_as(list))
    _plan_info_not_null = field_validator("plan_info", mode="before")(_null_as(dict))


class ActivityView(BaseModel):
    name: str | None = None
    hours: float | None = None


class DisciplineView(BaseModel):
    name: str | None = None
    module: str
    credits: int | None = None
    hours: float
    control_type: str | None = None
    activities: list[ActivityView]


class StudyPlanView(BaseModel):
    plan_id: int | None = None
    semester: int | None = None
    total_credits: int
    disciplines: list[DisciplineView]
