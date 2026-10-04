from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from mcp_my_itmo.features.finances.models import PaymentContract

# Shapes per go-itmo (myitmo/dormitory.go); live-verify pending.


def _empty_if_none(value):
    return [] if value is None else value


class AssignedDormitory(BaseModel):
    building_id: int | None = Field(default=None, alias="buildingId")
    name: str | None = None
    address: str | None = None
    settlement_procedure_text: str | None = Field(default=None, alias="settlementProcedureText")


class Appointment(BaseModel):
    time_slot: str | None = Field(default=None, alias="timeSlot")
    can_remove_until: str | None = Field(default=None, alias="canRemoveUntil")


class DormitoryStatus(BaseModel):
    """statusId: 1 queued, 2 place offered, 3 check-in booked, 4 settled."""

    status_id: int | None = Field(default=None, alias="statusId")
    dorm_type: str | None = Field(default=None, alias="dormType")
    queue_place: int | None = Field(default=None, alias="queuePlace")
    assigned_dormitory: AssignedDormitory | None = Field(default=None, alias="assignedDormitory")
    appointment: Appointment | None = None


class DormitoryPeriod(BaseModel):
    year: int | None = None
    date_from: str | None = Field(default=None, alias="dateFrom")
    date_to: str | None = Field(default=None, alias="dateTo")


class PeriodContracts(BaseModel):
    year: int | None = None
    contracts: Annotated[list[PaymentContract], BeforeValidator(_empty_if_none)] = Field(
        default_factory=list
    )
