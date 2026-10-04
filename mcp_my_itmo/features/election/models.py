from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _null_as_empty_list(value):
    return [] if value is None else value


class ElectionDisciplineSemester(BaseModel):
    semester: int | None = None
    status_id: int | None = Field(default=None, alias="statusId")
    status_name: str | None = Field(default=None, alias="statusName")
    group_flow: str | None = Field(default=None, alias="groupFlow")


class ElectionDiscipline(BaseModel):
    """A discipline offered by the /api/election campaign."""

    disc_id: int = Field(alias="discId")
    disc_name: str | None = Field(default=None, alias="discName")
    dep_name: str | None = Field(default=None, alias="depName")
    lang_code: str | None = Field(default=None, alias="langCode")
    required: bool | None = None
    description: str | None = None
    semesters: list[ElectionDisciplineSemester] = Field(default_factory=list)
    not_compatible_with: list[int] = Field(default_factory=list, alias="notCompatibleWith")

    _lists_default = field_validator("semesters", "not_compatible_with", mode="before")(
        _null_as_empty_list
    )


class ElectiveNode(BaseModel):
    """A node of the intro/facultative tree: group, module, discipline or flow, nested in variants."""

    id: int | None = None
    name: str | None = None
    required: bool | None = None
    selections: list[int] = Field(default_factory=list)
    language: str | None = None
    work_type: int | None = None
    teachers: list[str] = Field(default_factory=list)
    flow_info: int | None = None
    variants: list[ElectiveNode] = Field(default_factory=list)

    _lists_default = field_validator("selections", "teachers", "variants", mode="before")(
        _null_as_empty_list
    )


class ElectivePeriod(BaseModel):
    date_start: str | None = None
    date_end: str | None = None
    choice_status: int | None = None
    semester: int | None = None
    study_year: str | None = None


class ElectiveFlowRef(BaseModel):
    flow_id: int | None = None
    date: str | None = None
    date_start: str | None = None


class ElectiveClash(BaseModel):
    flow1: ElectiveFlowRef | None = None
    flow2: ElectiveFlowRef | None = None
    intersection_type: int | None = None


class ElectiveCurrent(BaseModel):
    """Own intro/facultative state: status 0 none, 1 booked (unconfirmed), 2 confirmed."""

    status: int | None = None
    flow_id: list[int] = Field(default_factory=list)
    intersections: list[ElectiveClash] = Field(default_factory=list)

    _lists_default = field_validator("flow_id", "intersections", mode="before")(
        _null_as_empty_list
    )


class ElectionAvailability(BaseModel):
    id: int | None = None
    status: str | None = None
    date_start: str | None = Field(default=None, alias="dateStart")
    date_end: str | None = Field(default=None, alias="dateEnd")
    time_start: str | None = Field(default=None, alias="timeStart")
    time_end: str | None = Field(default=None, alias="timeEnd")
    study_year: str | None = Field(default=None, alias="studyYear")
    semester: int | None = None


class ElectionFlow(BaseModel):
    id: int | None = None
    name: str | None = None
    teachers: list[str] = Field(default_factory=list)
    work_type: int | None = Field(default=None, alias="workType")
    available: bool | None = None
    variants: list[ElectionFlow] = Field(default_factory=list)

    _lists_default = field_validator("teachers", "variants", mode="before")(
        _null_as_empty_list
    )


class ElectionFlowChain(BaseModel):
    discipline_id: int | None = Field(default=None, alias="disciplineId")
    discipline_name: str | None = Field(default=None, alias="disciplineName")
    group_flow: str | None = Field(default=None, alias="groupFlow")
    flows: list[ElectionFlow] = Field(default_factory=list)

    _flows_default = field_validator("flows", mode="before")(_null_as_empty_list)
