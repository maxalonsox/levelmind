from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import PlanningStatus
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.generated_plan import PersistedMission, PersistedStage
from app.schemas.plan import (
    GoalPlanMission,
    GoalPlanResponse,
    GoalPlanStage,
    PlanProgress,
)
from app.services.goal import get_owned_goal


def get_goal_plan(
    db: Session, goal_id: UUID, user_id: UUID
) -> GoalPlanResponse:
    goal = get_owned_goal(db, goal_id, user_id)
    stages = list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .options(
                selectinload(Stage.missions).selectinload(Mission.tasks)
            )
            .order_by(Stage.order_index.asc())
        )
    )

    tasks: list[Task] = []
    response_stages: list[GoalPlanStage] = []
    for stage in stages:
        stage.missions.sort(key=lambda mission: mission.order_index)
        response_missions: list[GoalPlanMission] = []
        for mission in stage.missions:
            mission.tasks.sort(key=lambda task: task.order_index)
            tasks.extend(mission.tasks)
            mission_data = PersistedMission.model_validate(mission).model_dump()
            response_missions.append(
                GoalPlanMission.model_validate(
                    {
                        **mission_data,
                        "estimated_duration_minutes": _total_duration(
                            mission.tasks
                        ),
                    }
                )
            )
        stage_tasks = [
            task for mission in stage.missions for task in mission.tasks
        ]
        stage_data = PersistedStage.model_validate(stage).model_dump(
            exclude={"missions"}
        )
        response_stages.append(
            GoalPlanStage.model_validate(
                {
                    **stage_data,
                    "missions": response_missions,
                    "estimated_duration_minutes": _total_duration(stage_tasks),
                }
            )
        )

    completed_tasks = sum(
        PlanningStatus(task.status) is PlanningStatus.COMPLETED
        for task in tasks
    )
    skipped_tasks = sum(
        PlanningStatus(task.status) is PlanningStatus.SKIPPED
        for task in tasks
    )
    total_tasks = len(tasks)
    pending_tasks = total_tasks - completed_tasks - skipped_tasks
    xp_earned = sum(
        task.xp_reward
        for task in tasks
        if PlanningStatus(task.status) is PlanningStatus.COMPLETED
    )
    percentage = (
        round(completed_tasks / total_tasks * 100, 2)
        if total_tasks
        else 0.0
    )

    return GoalPlanResponse.model_validate(
        {
            "goal_id": goal.id,
            "status": goal.status,
            "progress": PlanProgress(
                percentage=percentage,
                xp_earned=xp_earned,
                level=xp_earned // 100 + 1,
                completed_tasks=completed_tasks,
                skipped_tasks=skipped_tasks,
                pending_tasks=pending_tasks,
                total_tasks=total_tasks,
            ),
            "stages": response_stages,
        }
    )


def _total_duration(tasks: list[Task]) -> int | None:
    if any(task.estimated_duration_minutes is None for task in tasks):
        return None
    return sum(task.estimated_duration_minutes or 0 for task in tasks)
