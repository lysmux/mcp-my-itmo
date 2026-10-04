from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.dormitory.models import (
    DormitoryPeriod,
    DormitoryStatus,
    PeriodContracts,
)
from mcp_my_itmo.features.finances.models import PaymentContract

# Routes per go-itmo (myitmo/dormitory.go, base /api/dormitory), live-verify pending.
# Mutating routes (register, cancel, pay, ...) are intentionally not exposed.


async def _read_result(client: MyItmoClient, path: str, params: dict | None = None):
    envelope = await client.get(path, params)
    if envelope.get("error_code"):
        raise ToolError(
            envelope.get("error_message") or f"Dormitory API error {envelope['error_code']}"
        )
    return envelope.get("result")


async def get_status(client: MyItmoClient) -> DormitoryStatus | None:
    raw = await _read_result(client, "/dormitory/status/full")
    return None if raw is None else DormitoryStatus.model_validate(raw)


async def get_payments(client: MyItmoClient) -> list[PeriodContracts]:
    raw_periods = await _read_result(client, "/dormitory/payments/contracts/periods") or []
    payments = []
    for raw_period in raw_periods:
        period = DormitoryPeriod.model_validate(raw_period)
        contracts = []
        if period.date_from and period.date_to:
            raw_contracts = await _read_result(
                client,
                "/dormitory/payments/contracts",
                {"from": period.date_from, "to": period.date_to},
            )
            contracts = [PaymentContract.model_validate(raw) for raw in raw_contracts or []]
        payments.append(PeriodContracts(year=period.year, contracts=contracts))
    return payments
