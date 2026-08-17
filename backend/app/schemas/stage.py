import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PlanningStatus


class StageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = Field(ge=0)
    status: PlanningStatus = PlanningStatus.PENDING


class StageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    status: PlanningStatus
    created_at: datetime
    updated_at: datetime
