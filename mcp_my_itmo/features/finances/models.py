from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

# Endpoints verified against go-itmo (myitmo/finances.go); live-verify pending.


def _flexible_amount(value):
    """Amounts arrive as numbers, numeric strings (decimal comma allowed) or null."""
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        return float(text) if text else None
    return value


def _flexible_id(value):
    return None if value is None else str(value)


def _flexible_flag(value):
    if isinstance(value, str):
        return value.strip() == "1" or value.strip().lower() == "true"
    return bool(value)


def _empty_if_none(value):
    return [] if value is None else value


Amount = Annotated[float | None, BeforeValidator(_flexible_amount)]
FlexId = Annotated[str | None, BeforeValidator(_flexible_id)]
Flag = Annotated[bool, BeforeValidator(_flexible_flag)]
ItemList = BeforeValidator(_empty_if_none)


class ScholarshipItem(BaseModel):
    item_name: str | None = None
    sum: float | None = None
    date_start: str | None = None
    date_end: str | None = None


class ScholarshipAccount(BaseModel):
    sum: float | None = None
    payment_items: Annotated[list[ScholarshipItem], ItemList] = Field(default_factory=list)


class IncomeLine(BaseModel):
    item_name: str | None = None
    account: str | None = None
    sum: float | None = None


class IncomeDetail(BaseModel):
    item_name: str | None = None
    sum: float | None = None


class IncomePayment(BaseModel):
    income: Annotated[list[IncomeLine], ItemList] = Field(default_factory=list)
    income_details: Annotated[list[IncomeDetail], ItemList] = Field(default_factory=list)


class ScholarshipIncomeMonth(BaseModel):
    payment_date: str | None = None
    payment: IncomePayment = Field(default_factory=IncomePayment)

    @field_validator("payment", mode="before")
    @classmethod
    def _null_payment_as_empty(cls, value):
        return {} if value is None else value


class ScholarshipTotal(BaseModel):
    category_id: int | None = None
    category_name: str | None = None
    sum: float | None = None

    @field_validator("category_name")
    @classmethod
    def _collapse_whitespace(cls, value):
        return None if value is None else " ".join(value.split())


class EduContract(BaseModel):
    contract_id: FlexId = Field(default=None, alias="contractId")
    number: str | None = None
    date_start: str | None = Field(default=None, alias="dateStart")
    date_end: str | None = Field(default=None, alias="dateEnd")
    active: Flag = False
    op: str | None = None
    period: str | None = None
    sum: Amount = None


class PaymentInstallment(BaseModel):
    period: str | None = None
    sum: Amount = None
    paid: Amount = None
    pay_until: str | None = Field(default=None, alias="payUntil")


class PaymentContract(BaseModel):
    contract_id: FlexId = Field(default=None, alias="contractId")
    name: str | None = None
    number: str | None = None
    date_start: str | None = Field(default=None, alias="dateStart")
    date_end: str | None = Field(default=None, alias="dateEnd")
    active: Flag = False
    balance: Amount = None
    payments: Annotated[list[PaymentInstallment], ItemList] = Field(default_factory=list)
