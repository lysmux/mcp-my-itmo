from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _null_as_empty_list(value):
    return [] if value is None else value


class RequestType(BaseModel):
    id: int
    name: str | None = None
    category_id: int | str | None = None
    category_name: str | None = None


class RequestSummary(BaseModel):
    id: int
    name: str | None = None
    notice: str | None = None
    status: int | None = None
    status_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class RequestApproval(BaseModel):
    fio: str | None = None
    context_name: str | None = None
    decision: str | None = None
    decision_date: str | None = None


class RequestEnteredField(BaseModel):
    name: str | None = None
    type: str | None = None
    data: str | None = None
    file_name: str | None = None
    multiple_data: dict | None = None


class RequestDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    request_name: str | None = None
    request_status: str | None = None
    request_state: str | None = None
    request_status_tag: str | None = None
    request_create_date: str | None = None
    approvals: list[RequestApproval] = Field(default_factory=list, alias="agreement_list")
    entered_fields: list[RequestEnteredField] = Field(default_factory=list)

    _lists_default = field_validator("approvals", "entered_fields", mode="before")(
        _null_as_empty_list
    )


class RequestField(BaseModel):
    field_id: int
    field_name: str | None = None
    field_note: str | None = None
    field_type: str | None = None
    required_field_flag: bool = False
    multiple_choice: bool | None = None
    dictionary_id: int | str | None = None


class RequestForm(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    template_description: str | None = None
    template_files: list[dict] = Field(default_factory=list)
    user_can_apply_now: bool = True
    user_cannot_apply_now_reason: str | None = None
    fields: list[RequestField] = Field(default_factory=list, alias="fields_data")

    _lists_default = field_validator("template_files", "fields", mode="before")(
        _null_as_empty_list
    )


class QueueSlot(BaseModel):
    time_table_id: int
    date: str | None = None


class QueueEntry(BaseModel):
    application_id: int
    type_id: int | None = None
    table_id: int | None = None
    table_name: str | None = None
    table_address: str | None = None
    date: str | None = None
    phone: str | None = None
    comment: str | None = None
    queue_comment: str | None = None


class Queue(BaseModel):
    table_id: int
    type_id: int | None = None
    table_name: str | None = None
    table_address: str | None = None
    comment: str | None = None
    template_id: int | None = None
    my_entries: list[QueueEntry] = Field(default_factory=list)
    slots: list[QueueSlot] | None = None
