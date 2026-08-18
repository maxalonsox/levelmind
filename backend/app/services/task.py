from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MemoryType, PlanningStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.memory_entry import MemoryEntryCreate
from app.schemas.task import (
    TaskCreate,
    TaskResultCreate,
    TaskResultResponse,
    TaskResponse,
)
from app.services.goal import get_owned_goal
from app.services.memory_entry import add_memory_entry


class TaskAlreadyResolvedError(Exception):
    """Raised when changing the result of an already resolved Task."""


def create_task(
    db: Session, data: TaskCreate, mission_id: UUID, user_id: UUID
) -> Task:
    _get_owned_mission(db, mission_id, user_id)
    task = Task(mission_id=mission_id, **data.model_dump())

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


def list_tasks(db: Session, mission_id: UUID, user_id: UUID) -> list[Task]:
    _get_owned_mission(db, mission_id, user_id)
    return list(
        db.scalars(
            select(Task)
            .where(Task.mission_id == mission_id)
            .order_by(Task.order_index.asc())
        )
    )


def resolve_task(
    db: Session,
    task_id: UUID,
    data: TaskResultCreate,
    user_id: UUID,
) -> TaskResultResponse:
    try:
        task = _get_owned_task(db, task_id, user_id, for_update=True)
        requested_status = PlanningStatus(data.result.value)
        current_status = PlanningStatus(task.status)

        if current_status in _TERMINAL_STATUSES:
            if current_status is not requested_status:
                raise TaskAlreadyResolvedError

            response = _result_response(task, xp_awarded=0)
            db.commit()
            return response

        mission = db.scalar(
            select(Mission)
            .where(Mission.id == task.mission_id)
            .with_for_update()
        )
        if mission is None:
            raise RuntimeError("Task has no parent Mission")

        stage = db.scalar(
            select(Stage)
            .where(Stage.id == mission.stage_id)
            .with_for_update()
        )
        if stage is None:
            raise RuntimeError("Mission has no parent Stage")

        goal = get_owned_goal(db, stage.goal_id, user_id, for_update=True)

        task.status = requested_status
        task.difficulty_feedback = data.difficulty_feedback
        task.feedback_text = data.feedback_text
        task.resolved_at = datetime.now(UTC)
        db.flush()

        mission.status = _derive_status(
            list(
                db.scalars(
                    select(Task.status).where(
                        Task.mission_id == mission.id
                    )
                )
            )
        )
        db.flush()

        stage.status = _derive_status(
            list(
                db.scalars(
                    select(Mission.status).where(
                        Mission.stage_id == stage.id
                    )
                )
            )
        )
        db.flush()

        stage_statuses = list(
            db.scalars(select(Stage.status).where(Stage.goal_id == goal.id))
        )
        if stage_statuses and all(
            PlanningStatus(value) is PlanningStatus.COMPLETED
            for value in stage_statuses
        ):
            goal.status = "completed"
        elif goal.status != "archived":
            goal.status = "active"

        add_memory_entry(
            db,
            MemoryEntryCreate(
                goal_id=goal.id,
                memory_type=MemoryType.OBSERVED,
                key="task_execution",
                value={
                    "result": data.result.value,
                    "estimated_difficulty": task.estimated_difficulty,
                    "difficulty_feedback": (
                        data.difficulty_feedback.value
                        if data.difficulty_feedback is not None
                        else None
                    ),
                },
                source_type="task",
                source_id=task.id,
                confidence=1.0,
            ),
            user_id,
        )

        xp_awarded = (
            task.xp_reward
            if requested_status is PlanningStatus.COMPLETED
            else 0
        )
        response = _result_response(task, xp_awarded=xp_awarded)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


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


def _result_response(task: Task, xp_awarded: int) -> TaskResultResponse:
    task_data = TaskResponse.model_validate(task).model_dump()
    return TaskResultResponse.model_validate(
        {**task_data, "xp_awarded": xp_awarded}
    )


def _get_owned_mission(db: Session, mission_id: UUID, user_id: UUID) -> Mission:
    mission = db.scalar(
        select(Mission)
        .join(Stage, Mission.stage_id == Stage.id)
        .join(Goal, Stage.goal_id == Goal.id)
        .where(Mission.id == mission_id, Goal.user_id == user_id)
    )
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        )
    return mission


def _get_owned_task(
    db: Session,
    task_id: UUID,
    user_id: UUID,
    *,
    for_update: bool = False,
) -> Task:
    statement = (
        select(Task)
        .join(Mission, Task.mission_id == Mission.id)
        .join(Stage, Mission.stage_id == Stage.id)
        .join(Goal, Stage.goal_id == Goal.id)
        .where(Task.id == task_id, Goal.user_id == user_id)
    )
    if for_update:
        statement = statement.with_for_update(of=Task)

    task = db.scalar(statement)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task
