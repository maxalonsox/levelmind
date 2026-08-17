from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Difficulty, PlanningStatus


class PlanRevisionTaskSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str | None
    order_index: int = Field(ge=0)
    estimated_duration_minutes: int | None
    estimated_difficulty: Difficulty | None
    xp_reward: int = Field(ge=0)
    status: PlanningStatus


class PlanRevisionMissionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str | None
    order_index: int = Field(ge=0)
    estimated_difficulty: Difficulty | None
    status: PlanningStatus
    tasks: list[PlanRevisionTaskSnapshot]


class PlanRevisionStageSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str | None
    order_index: int = Field(ge=0)
    status: PlanningStatus
    missions: list[PlanRevisionMissionSnapshot]


class PlanRevisionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stages: list[PlanRevisionStageSnapshot]
