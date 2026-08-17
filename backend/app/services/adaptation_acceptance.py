from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.adaptation.contracts import (
    AdaptationDecision,
    AdaptationMissionOutline,
    AdaptationProposal,
    AdaptationStageOutline,
    AdaptationTaskOutline,
    AdaptationTaskTarget,
    AddTaskChange,
    AdjustTaskDifficultyChange,
    AdjustTaskDurationChange,
    ReorderTaskChange,
    ReplaceTaskChange,
    SplitTaskChange,
)
from app.ai.adaptation.errors import InvalidAdaptationTargetError
from app.models.enums import AdaptationStatus, PlanningStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.plan_adaptation import PlanAdaptation
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.adaptation import AdaptationAcceptResponse
from app.services.adaptation import (
    validate_adaptation_targets_against_outline,
)
from app.services.goal import get_owned_goal
from app.services.plan_revision import (
    create_plan_revision,
    get_current_plan_revision,
)


class AdaptationAcceptanceConflictError(Exception):
    """Raised when a persisted adaptation cannot be safely accepted."""


@dataclass
class _LockedPlan:
    stages: list[Stage]
    missions: list[Mission]
    tasks: list[Task]


def accept_plan_adaptation(
    db: Session,
    goal_id: UUID,
    adaptation_id: UUID,
    user_id: UUID,
) -> AdaptationAcceptResponse:
    try:
        get_owned_goal(db, goal_id, user_id)
        adaptation = db.scalar(
            select(PlanAdaptation)
            .where(
                PlanAdaptation.id == adaptation_id,
                PlanAdaptation.goal_id == goal_id,
            )
            .with_for_update()
        )
        if adaptation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Adaptation not found",
            )
        if AdaptationStatus(adaptation.status) is not AdaptationStatus.PENDING:
            raise AdaptationAcceptanceConflictError(
                "Adaptation has already been reviewed"
            )
        if adaptation.base_revision_id is None:
            raise AdaptationAcceptanceConflictError(
                "Adaptation has no verifiable base revision"
            )

        plan = _lock_plan(db, goal_id)
        goal = get_owned_goal(db, goal_id, user_id, for_update=True)
        current_revision = get_current_plan_revision(
            db, goal_id, for_update=True
        )
        if (
            current_revision is None
            or current_revision.id != adaptation.base_revision_id
        ):
            raise AdaptationAcceptanceConflictError(
                "Adaptation was created for an obsolete plan revision"
            )

        try:
            proposal = AdaptationProposal.model_validate(adaptation.proposal)
        except ValidationError as exc:
            raise AdaptationAcceptanceConflictError(
                "Stored adaptation proposal is invalid"
            ) from exc
        if proposal.decision is not AdaptationDecision.PROPOSE_CHANGES:
            raise AdaptationAcceptanceConflictError(
                "Stored adaptation does not propose changes"
            )

        outline = _plan_outline(plan)
        try:
            validate_adaptation_targets_against_outline(proposal, outline)
        except InvalidAdaptationTargetError as exc:
            raise AdaptationAcceptanceConflictError(
                "Adaptation targets no longer match the current plan"
            ) from exc

        _apply_changes(db, plan, proposal)
        db.flush()
        _refresh_parent_statuses(plan, goal, db)
        db.flush()

        reviewed_at = datetime.now(UTC)
        adaptation.status = AdaptationStatus.ACCEPTED
        adaptation.reviewed_at = reviewed_at
        db.flush()
        revision = create_plan_revision(
            db,
            goal_id,
            base_revision=current_revision,
            adaptation_id=adaptation.id,
        )
        response = AdaptationAcceptResponse(
            adaptation_id=adaptation.id,
            status=AdaptationStatus.ACCEPTED,
            reviewed_at=reviewed_at,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            applied_change_count=len(proposal.changes),
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def _lock_plan(db: Session, goal_id: UUID) -> _LockedPlan:
    tasks = list(
        db.scalars(
            select(Task)
            .join(Mission, Task.mission_id == Mission.id)
            .join(Stage, Mission.stage_id == Stage.id)
            .where(Stage.goal_id == goal_id)
            .order_by(Task.id)
            .with_for_update(of=Task)
        )
    )
    missions = list(
        db.scalars(
            select(Mission)
            .join(Stage, Mission.stage_id == Stage.id)
            .where(Stage.goal_id == goal_id)
            .order_by(Mission.id)
            .with_for_update(of=Mission)
        )
    )
    stages = list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .order_by(Stage.id)
            .with_for_update(of=Stage)
        )
    )
    return _LockedPlan(stages=stages, missions=missions, tasks=tasks)


def _plan_outline(plan: _LockedPlan) -> list[AdaptationStageOutline]:
    missions_by_stage: dict[UUID, list[Mission]] = {}
    tasks_by_mission: dict[UUID, list[Task]] = {}
    for mission in plan.missions:
        missions_by_stage.setdefault(mission.stage_id, []).append(mission)
    for task in plan.tasks:
        tasks_by_mission.setdefault(task.mission_id, []).append(task)

    return [
        AdaptationStageOutline(
            order_index=stage.order_index,
            title=stage.title,
            missions=[
                AdaptationMissionOutline(
                    order_index=mission.order_index,
                    title=mission.title,
                    tasks=[
                        AdaptationTaskOutline(
                            order_index=task.order_index,
                            title=task.title,
                            status=PlanningStatus(task.status),
                            estimated_difficulty=task.estimated_difficulty,
                        )
                        for task in sorted(
                            tasks_by_mission.get(mission.id, []),
                            key=lambda item: item.order_index,
                        )
                    ],
                )
                for mission in sorted(
                    missions_by_stage.get(stage.id, []),
                    key=lambda item: item.order_index,
                )
            ],
        )
        for stage in sorted(plan.stages, key=lambda item: item.order_index)
    ]


def _apply_changes(
    db: Session, plan: _LockedPlan, proposal: AdaptationProposal
) -> None:
    stages_by_id = {stage.id: stage for stage in plan.stages}
    missions = {
        (
            stages_by_id[mission.stage_id].order_index,
            mission.order_index,
        ): mission
        for mission in plan.missions
    }
    tasks_by_mission = {
        mission.id: sorted(
            [task for task in plan.tasks if task.mission_id == mission.id],
            key=lambda item: item.order_index,
        )
        for mission in plan.missions
    }
    original_tasks = {
        (stage_index, mission_index, task.order_index): task
        for (stage_index, mission_index), mission in missions.items()
        for task in tasks_by_mission[mission.id]
    }
    targeted_task_ids: set[UUID] = set()

    for change in proposal.changes:
        mission = missions[
            (change.target.stage_order_index, change.target.mission_order_index)
        ]
        siblings = tasks_by_mission[mission.id]

        if isinstance(change, AddTaskChange):
            task = Task(
                mission_id=mission.id,
                title=change.task.title,
                description=change.task.description,
                order_index=0,
                estimated_duration_minutes=(
                    change.task.estimated_duration_minutes
                ),
                estimated_difficulty=None,
                xp_reward=change.task.xp_reward,
                status=PlanningStatus.PENDING,
            )
            if change.insert_after_task_order_index is None:
                insertion_index = 0
            else:
                anchor = original_tasks[
                    (
                        change.target.stage_order_index,
                        change.target.mission_order_index,
                        change.insert_after_task_order_index,
                    )
                ]
                if anchor not in siblings:
                    raise AdaptationAcceptanceConflictError(
                        "Add Task insertion target was changed by the proposal"
                    )
                insertion_index = siblings.index(anchor) + 1
            siblings.insert(insertion_index, task)
            db.add(task)
            continue

        target = _target_task(change.target, original_tasks)
        if target.id in targeted_task_ids:
            raise AdaptationAcceptanceConflictError(
                "A Task cannot be changed more than once in one adaptation"
            )
        targeted_task_ids.add(target.id)
        if PlanningStatus(target.status) in _TERMINAL_STATUSES:
            raise AdaptationAcceptanceConflictError(
                "Resolved Tasks cannot be changed by an adaptation"
            )

        if isinstance(change, SplitTaskChange):
            if target not in siblings:
                raise AdaptationAcceptanceConflictError(
                    "Split Task target was changed by the proposal"
                )
            target_index = siblings.index(target)
            replacements = [
                Task(
                    mission_id=mission.id,
                    title=replacement.title,
                    description=replacement.description,
                    order_index=0,
                    estimated_duration_minutes=(
                        replacement.estimated_duration_minutes
                    ),
                    estimated_difficulty=None,
                    xp_reward=replacement.xp_reward,
                    status=PlanningStatus.PENDING,
                )
                for replacement in change.replacement_tasks
            ]
            siblings[target_index : target_index + 1] = replacements
            db.delete(target)
            db.add_all(replacements)
        elif isinstance(change, ReplaceTaskChange):
            target.title = change.replacement.title
            target.description = change.replacement.description
            target.estimated_duration_minutes = (
                change.replacement.estimated_duration_minutes
            )
            target.estimated_difficulty = None
            target.xp_reward = change.replacement.xp_reward
        elif isinstance(change, ReorderTaskChange):
            destination = original_tasks[
                (
                    change.target.stage_order_index,
                    change.target.mission_order_index,
                    change.destination_order_index,
                )
            ]
            if target not in siblings or destination not in siblings:
                raise AdaptationAcceptanceConflictError(
                    "Reorder Task references a Task changed by the proposal"
                )
            destination_index = siblings.index(destination)
            siblings.remove(target)
            siblings.insert(destination_index, target)
        elif isinstance(change, AdjustTaskDifficultyChange):
            target.estimated_difficulty = change.proposed_difficulty
        elif isinstance(change, AdjustTaskDurationChange):
            target.estimated_duration_minutes = (
                change.estimated_duration_minutes
            )
        else:
            raise AdaptationAcceptanceConflictError(
                "Stored adaptation contains an unsupported change"
            )

    for siblings in tasks_by_mission.values():
        titles = [task.title for task in siblings]
        if len(titles) != len(set(titles)):
            raise AdaptationAcceptanceConflictError(
                "Adaptation would create duplicate Tasks in a Mission"
            )
        for order_index, task in enumerate(siblings):
            task.order_index = order_index


def _target_task(
    target: AdaptationTaskTarget,
    original_tasks: dict[tuple[int, int, int], Task],
) -> Task:
    return original_tasks[
        (
            target.stage_order_index,
            target.mission_order_index,
            target.task_order_index,
        )
    ]


def _refresh_parent_statuses(
    plan: _LockedPlan, goal: Goal, db: Session
) -> None:
    for mission in plan.missions:
        statuses = list(
            db.scalars(
                select(Task.status).where(Task.mission_id == mission.id)
            )
        )
        mission.status = _derive_status(statuses)
    db.flush()

    for stage in plan.stages:
        statuses = list(
            db.scalars(
                select(Mission.status).where(Mission.stage_id == stage.id)
            )
        )
        stage.status = _derive_status(statuses)
    db.flush()

    stage_statuses = [PlanningStatus(stage.status) for stage in plan.stages]
    if stage_statuses and all(
        value is PlanningStatus.COMPLETED for value in stage_statuses
    ):
        goal.status = "completed"
    elif goal.status != "archived":
        goal.status = "active"


_TERMINAL_STATUSES = {
    PlanningStatus.COMPLETED,
    PlanningStatus.SKIPPED,
}


def _derive_status(statuses: list[str]) -> PlanningStatus:
    normalized = [PlanningStatus(value) for value in statuses]
    if not normalized or all(
        value is PlanningStatus.PENDING for value in normalized
    ):
        return PlanningStatus.PENDING
    if all(value is PlanningStatus.COMPLETED for value in normalized):
        return PlanningStatus.COMPLETED
    if all(value in _TERMINAL_STATUSES for value in normalized):
        return PlanningStatus.SKIPPED
    return PlanningStatus.IN_PROGRESS
