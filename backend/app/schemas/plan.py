from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.generated_plan import PersistedMission, PersistedStage


class GoalPlanMission(PersistedMission):
    estimated_duration_minutes: int | None = Field(default=None, ge=0)


class GoalPlanStage(PersistedStage):
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    missions: list[GoalPlanMission]


class PlanProgress(BaseModel):
    percentage: float = Field(ge=0, le=100)
    xp_earned: int = Field(ge=0)
    level: int = Field(ge=1)
    completed_tasks: int = Field(ge=0)
    skipped_tasks: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    total_tasks: int = Field(ge=0)


class GoalPlanResponse(BaseModel):
    goal_id: UUID
    status: str
    progress: PlanProgress
    stages: list[GoalPlanStage]
