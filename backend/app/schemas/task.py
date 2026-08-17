import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Difficulty, PlanningStatus, TaskResult


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = Field(ge=0)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    status: PlanningStatus = PlanningStatus.PENDING
    difficulty_feedback: Difficulty | None = None
    feedback_text: str | None = None
    xp_reward: int = Field(default=10, ge=0)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    estimated_duration_minutes: int | None
    status: PlanningStatus
    difficulty_feedback: Difficulty | None
    feedback_text: str | None
    resolved_at: datetime | None
    xp_reward: int
    created_at: datetime
    updated_at: datetime


class TaskResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    result: TaskResult
    difficulty_feedback: Difficulty | None = None
    feedback_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )


class TaskResultResponse(TaskResponse):
    xp_awarded: int = Field(ge=0)
