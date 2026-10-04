from __future__ import annotations

from mcp_my_itmo.core.client import MyItmoClient
from mcp_my_itmo.features.study_plan.models import (
    ActivityView,
    Content,
    DisciplineView,
    PlanNode,
    StudyPlan,
    StudyPlanView,
    StudyProgram,
    StudyPrograms,
)
from mcp_my_itmo.logging_setup import get_logger

log = get_logger(__name__)

# Routes and structs per go-itmo (myitmo/studyplan.go), live-verify pending.
# Both responses are {error_code, error_message, result} with an OBJECT result.
# The legacy /api/eduPlan routes only mutate choices and are intentionally not exposed.

_EXAM_WORK_TYPE = 5
_CREDIT_WORK_TYPE = 6
_CONTROL_TYPES = {_EXAM_WORK_TYPE: "exam", _CREDIT_WORK_TYPE: "credit"}


class StudyPlanSelectionError(Exception):
    """Raised when no matching study plan is available."""


async def list_study_plans(client: MyItmoClient) -> list[StudyProgram]:
    envelope = await client.get("/eduPlanNew/programs")
    return StudyPrograms.model_validate(envelope.get("result") or {}).programs


async def get_study_plan(
    client: MyItmoClient, semester: int | None = None, plan_id: int | None = None
) -> StudyPlanView:
    program = _pick_program(await list_study_plans(client), plan_id)
    params = (
        {"spec_id": program.specialization_id}
        if program.specialization_id is not None
        else None
    )
    log.debug("study_plan.fetch", plan_id=program.plan_id, semester=semester)
    envelope = await client.get(f"/eduPlanNew/study_plan/{program.plan_id}", params=params)
    plan = StudyPlan.model_validate(envelope.get("result") or {})
    semester = semester if semester is not None else plan.current_semester
    disciplines = [] if semester is None else _disciplines_of(plan.structure, semester)
    return StudyPlanView(
        plan_id=program.plan_id,
        semester=semester,
        total_credits=sum(d.credits or 0 for d in disciplines),
        disciplines=disciplines,
    )


def _pick_program(programs: list[StudyProgram], plan_id: int | None) -> StudyProgram:
    if plan_id is not None:
        for program in programs:
            if program.plan_id == plan_id:
                return program
        raise StudyPlanSelectionError(f"Unknown study plan {plan_id}.")
    if not programs:
        raise StudyPlanSelectionError("No study plans available.")
    return next((program for program in programs if program.is_active), programs[0])


def _disciplines_of(
    nodes: list[PlanNode], semester: int, path: tuple[str, ...] = ()
) -> list[DisciplineView]:
    found: list[DisciplineView] = []
    for node in nodes:
        for content in node.contents.get(str(semester), []):
            found.append(_discipline_view(node, content, path))
        found.extend(_disciplines_of(node.children, semester, (*path, node.name or "")))
    return found


def _discipline_view(node: PlanNode, content: Content, path: tuple[str, ...]) -> DisciplineView:
    worked = [a for a in content.activities if a.volume is not None]
    return DisciplineView(
        name=node.name,
        module=" / ".join(part for part in path if part),
        credits=content.credit_points,
        hours=sum(a.volume for a in worked),
        control_type=next(
            (
                _CONTROL_TYPES[a.work_type_id]
                for a in content.activities
                if a.work_type_id in _CONTROL_TYPES
            ),
            None,
        ),
        activities=[ActivityView(name=a.name, hours=a.volume) for a in worked],
    )
