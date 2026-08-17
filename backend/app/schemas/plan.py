from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.generated_plan import PersistedStage


class PlanProgress(BaseModel):
    percentage: float = Field(ge=0, le=100)
    xp_earned: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    skipped_tasks: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    total_tasks: int = Field(ge=0)


class GoalPlanResponse(BaseModel):
    goal_id: UUID
    status: str
    progress: PlanProgress
    stages: list[PersistedStage]
