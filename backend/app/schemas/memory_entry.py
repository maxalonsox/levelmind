from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MemoryType

JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class MemoryEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: UUID | None = None
    memory_type: MemoryType
    key: str = Field(min_length=1, max_length=100)
    value: JsonValue
    source_type: str = Field(min_length=1, max_length=50)
    source_id: UUID | None = None
    confidence: float = Field(ge=0, le=1)


class MemoryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    goal_id: UUID | None
    memory_type: MemoryType
    key: str
    value: JsonValue
    source_type: str
    source_id: UUID | None
    confidence: float
    created_at: datetime
