from collections.abc import Sequence
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Difficulty
from app.schemas.mission import MissionResponse
from app.schemas.stage import StageResponse
from app.schemas.task import TaskResponse


class _OrderedItem(Protocol):
    order_index: int


def _ensure_unique_order_indexes(
    items: Sequence[_OrderedItem], level_name: str
) -> None:
    order_indexes = [item.order_index for item in items]
    if len(order_indexes) != len(set(order_indexes)):
        raise ValueError(f"Duplicate order_index in {level_name}")


class GeneratedTask(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = Field(ge=0)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    xp_reward: int = Field(default=10, ge=0)


class GeneratedMission(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = Field(ge=0)
    estimated_difficulty: Difficulty | None = None
    tasks: list[GeneratedTask] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_task_order_indexes(self) -> Self:
        _ensure_unique_order_indexes(self.tasks, "mission tasks")
        return self


class GeneratedStage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = Field(ge=0)
    missions: list[GeneratedMission] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mission_order_indexes(self) -> Self:
        _ensure_unique_order_indexes(self.missions, "stage missions")
        return self


class GeneratedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stages: list[GeneratedStage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_stage_order_indexes(self) -> Self:
        _ensure_unique_order_indexes(self.stages, "plan stages")
        return self


class PersistedMission(MissionResponse):
    tasks: list[TaskResponse]


class PersistedStage(StageResponse):
    missions: list[PersistedMission]


class PersistedPlan(BaseModel):
    stages: list[PersistedStage]
