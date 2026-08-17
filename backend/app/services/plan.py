from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import PlanningStatus
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.plan import GoalPlanResponse, PlanProgress
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
    for stage in stages:
        stage.missions.sort(key=lambda mission: mission.order_index)
        for mission in stage.missions:
            mission.tasks.sort(key=lambda task: task.order_index)
            tasks.extend(mission.tasks)

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
                completed_tasks=completed_tasks,
                skipped_tasks=skipped_tasks,
                pending_tasks=pending_tasks,
                total_tasks=total_tasks,
            ),
            "stages": stages,
        }
    )
