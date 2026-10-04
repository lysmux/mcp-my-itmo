from mcp.server.fastmcp import FastMCP

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.errors import tool_errors
from mcp_my_itmo.features.finances import api


def register(app: FastMCP, client: MyItmoClient) -> None:
    @app.tool()
    @tool_errors
    async def get_scholarship_account() -> list[dict]:
        """Assigned scholarships with their payment items (amounts in roubles)."""
        accounts = await api.get_scholarship_accounts(client)
        return [account.model_dump() for account in accounts]

    @app.tool()
    @tool_errors
    async def get_scholarship_income() -> list[dict]:
        """Monthly scholarship income history: transfers and accrual details per month."""
        months = await api.get_scholarship_income(client)
        return [month.model_dump() for month in months]

    @app.tool()
    @tool_errors
    async def get_scholarship_totals(
        date_from: str | None = None, date_to: str | None = None
    ) -> list[dict]:
        """Scholarship totals per finance category. Optional YYYY-MM-DD range; omit both for all time."""
        totals = await api.get_scholarship_totals(client, date_from, date_to)
        return [total.model_dump() for total in totals]

    @app.tool()
    @tool_errors
    async def list_edu_contracts() -> list[dict]:
        """Paid-tuition contracts; the first one is the current contract."""
        contracts = await api.get_edu_contracts(client)
        return [contract.model_dump() for contract in contracts]

    @app.tool()
    @tool_errors
    async def get_edu_payments() -> list[dict]:
        """Tuition and dormitory payment schedules; sum minus paid is still due, a debt after pay_until."""
        contracts = await api.get_edu_payments(client)
        return [contract.model_dump() for contract in contracts]
