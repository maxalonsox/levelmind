import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    current_situation: str = Field(
        min_length=1,
    )

    expected_outcome: str = Field(
        min_length=1,
    )

    target_timeframe: str | None = Field(
        default=None,
        max_length=100,
    )

    availability: str | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    current_situation: str
    expected_outcome: str
    target_timeframe: str | None
    availability: str | None
    status: str
    created_at: datetime
    updated_at: datetime
