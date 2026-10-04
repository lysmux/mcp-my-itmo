from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.core.envelope import unwrap_result
from mcp_my_itmo.features.record_book.models import Specialization, SubjectMark
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)


class RecordBookSelectionError(Exception):
    """Raised when the requested specialization or semester does not exist."""


async def list_specializations(client: MyItmoClient) -> list[Specialization]:
    envelope = await client.get("/record_book/specializations")
    return [Specialization.model_validate(raw) for raw in unwrap_result(envelope)]


async def get_record_book(
    client: MyItmoClient, specialization_id: int | None = None, semester: int | None = None
) -> list[SubjectMark]:
    if specialization_id is None or semester is None:
        specialization = _pick_specialization(
            await list_specializations(client), specialization_id
        )
        specialization_id = specialization.main_plan
        if semester is None:
            semester = _default_semester(specialization)
    log.debug("record_book.fetch", main_plan=specialization_id, semester=semester)
    envelope = await client.get(f"/record_book/{specialization_id}/{semester}")
    return [SubjectMark.model_validate(raw) for raw in unwrap_result(envelope)]


def _pick_specialization(
    specializations: list[Specialization], main_plan: int | None
) -> Specialization:
    if main_plan is not None:
        for specialization in specializations:
            if specialization.main_plan == main_plan:
                return specialization
        raise RecordBookSelectionError(f"Unknown specialization {main_plan}.")
    if not specializations:
        raise RecordBookSelectionError("No specializations available.")
    return specializations[0]


def _default_semester(specialization: Specialization) -> int:
    semesters = specialization.semesters
    if not semesters:
        raise RecordBookSelectionError("The specialization has no semesters.")
    for info in semesters:
        if info.actual:
            return info.semester
    return max(info.semester for info in semesters)
