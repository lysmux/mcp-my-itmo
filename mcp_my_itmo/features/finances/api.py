from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import unwrap_result
from mcp_my_itmo.core.errors import parse_optional_date
from mcp_my_itmo.features.finances.models import (
    EduContract,
    PaymentContract,
    ScholarshipAccount,
    ScholarshipIncomeMonth,
    ScholarshipTotal,
)

# Endpoints verified against go-itmo (myitmo/finances.go); live-verify pending.
# Salary endpoints are staff-only and intentionally not exposed.


async def get_scholarship_accounts(client: MyItmoClient) -> list[ScholarshipAccount]:
    envelope = await client.get("/finances/scholarship/account")
    return [ScholarshipAccount.model_validate(raw) for raw in unwrap_result(envelope)]


async def get_scholarship_income(client: MyItmoClient) -> list[ScholarshipIncomeMonth]:
    envelope = await client.get("/finances/scholarship/income")
    return [ScholarshipIncomeMonth.model_validate(raw) for raw in unwrap_result(envelope)]


async def get_scholarship_totals(
    client: MyItmoClient, date_from: str | None = None, date_to: str | None = None
) -> list[ScholarshipTotal]:
    params = {
        key: day.isoformat()
        for key, day in (
            ("dateFrom", parse_optional_date(date_from)),
            ("dateTo", parse_optional_date(date_to)),
        )
        if day is not None
    }
    envelope = await client.get("/finances/scholarship/total", params=params or None)
    return [ScholarshipTotal.model_validate(raw) for raw in unwrap_result(envelope)]


async def get_edu_contracts(client: MyItmoClient) -> list[EduContract]:
    envelope = await client.get("/finances/edupayments/contracts")
    return [EduContract.model_validate(raw) for raw in unwrap_result(envelope)]


async def get_edu_payments(client: MyItmoClient) -> list[PaymentContract]:
    envelope = await client.get("/finances/edupayments/payments")
    return [PaymentContract.model_validate(raw) for raw in unwrap_result(envelope)]
