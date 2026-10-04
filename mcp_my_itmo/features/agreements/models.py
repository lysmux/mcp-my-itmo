from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator


def _id_as_str(value):
    return None if value is None else str(value)


def _status_as_int(value):
    if value is None or value == "":
        return None
    return int(value)


FlexId = Annotated[str | None, BeforeValidator(_id_as_str)]


class AgreementVersion(BaseModel):
    """One version of an agreement; ids arrive as numbers or strings."""

    id: FlexId = None
    date: str | None = None
    status_id: Annotated[int | None, BeforeValidator(_status_as_int)] = None
    status_name: str | None = None
    date_signed: str | None = None
    date_revoked: str | None = None
    reject_reason: str | None = None
    task_id: str | None = None
    signature_id: str | None = None


class Agreement(BaseModel):
    """A consent or document to acknowledge, with its version history."""

    id: FlexId = None
    title: str | None = None
    versions: list[AgreementVersion] = Field(default_factory=list)

    @field_validator("versions", mode="before")
    @classmethod
    def _null_as_empty_list(cls, value):
        return [] if value is None else value

    def latest_version(self) -> AgreementVersion | None:
        dated = [version for version in self.versions if version.date]
        if dated:
            return max(dated, key=lambda version: version.date)
        return self.versions[-1] if self.versions else None


class AgreementSignTask(BaseModel):
    task_id: str | None = None
    signature_id: str | None = None
