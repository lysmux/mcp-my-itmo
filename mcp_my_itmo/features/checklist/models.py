from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

# Shapes per go-itmo (myitmo/checklist.go), live-verify pending.


def _actions_or_empty(value):
    """Department actions arrive as a list or as an empty string."""
    return value if isinstance(value, list) else []


ItemList = BeforeValidator(lambda value: [] if value is None else value)


class ChecklistItem(BaseModel):
    problem: str | None = None
    decision: str | None = None
    decision_id: int | None = None
    comment: str | None = None
    action: str | None = None
    url: str | None = None
    action_id: int | None = None


class ChecklistAction(BaseModel):
    action: str | None = None
    action_id: int | None = None
    comment: str | None = None


class ChecklistDepartment(BaseModel):
    department: str | None = None
    problem: str | None = None
    decision: str | None = None
    decision_id: int | None = None
    contact_person_name: str | None = None
    comment: str | None = None
    actions: Annotated[list[ChecklistAction], BeforeValidator(_actions_or_empty)] = Field(
        default_factory=list
    )


class ChecklistBypass(BaseModel):
    student: Annotated[list[ChecklistItem], ItemList] = Field(default_factory=list)
    departments: Annotated[list[ChecklistDepartment], ItemList] = Field(default_factory=list)
