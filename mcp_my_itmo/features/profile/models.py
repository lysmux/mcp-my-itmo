from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Profile(BaseModel):
    isu: int | None = None
    preferred_username: str | None = None
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    middle_name: str | None = None
    email: str | None = None
    edu_email: str | None = None
    birthdate: str | None = None
    gender: str | None = None
    groups: list[str] = Field(default_factory=list)
    is_student: bool | None = None

    @field_validator("groups", mode="before")
    @classmethod
    def _null_groups_as_empty(cls, value):
        return [] if value is None else value
